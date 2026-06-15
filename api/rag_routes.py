"""RAG API Routes - Document processing and retrieval"""
import os
import io
import json
import uuid
import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from PIL import Image
import PyPDF2
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy import create_engine, Column, String, Text, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import logging
import time

logger = logging.getLogger(__name__)

# Import config
from config import (
    OLAMA_HOST,
    OLAMA_MODEL,
    DATABASE_URL,
    FAISS_INDEX_PATH,
    FAISS_META_PATH,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
    HF_TIMEOUT,
)

# ---- Configure requests with retry + timeout ----
def configure_requests_session():
    """Configure requests with exponential backoff + longer timeout"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

requests_session = configure_requests_session()
logger.info(f"✓ Requests configured with {HF_TIMEOUT}s timeout and retry strategy")

# ---- Create data dir ----
os.makedirs("./data", exist_ok=True)

# ---- DB Setup ----
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    source = Column(String, index=True)
    chunk_index = Column(Integer)
    text = Column(Text)
    meta_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    embedding_dim = Column(Integer)

Base.metadata.create_all(bind=engine)

# ---- Models ----
logger.info("Loading embedding model (this may take a minute on first run)...")
try:
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    embedding_dim = embedder.get_sentence_embedding_dimension()
    logger.info(f"✓ Embedding model loaded ({embedding_dim} dimensions)")
except Exception as e:
    logger.error(f"❌ Failed to load embedding model: {e}")
    logger.info("💡 Try: HF_HUB_TIMEOUT=120 python main.py")
    raise

# Image captioner - optional (slow first load)
try:
    logger.info("Loading vision model (this may take a minute on first run)...")
    vision_model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    vision_processor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    vision_tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    HAS_VISION = True
    logger.info("✓ Vision model loaded")
except Exception as e:
    HAS_VISION = False
    vision_model = vision_processor = vision_tokenizer = None
    logger.warning(f"⚠️  Vision model not available: {e}")

# ---- FAISS Vector Store ----
class VectorStore:
    def __init__(self, dim, index_path, meta_path):
        self.dim = dim
        self.index_path = index_path
        self.meta_path = meta_path
        self.metadatas = []
        self.index = None
        self.load_or_create()

    def load_or_create(self):
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.meta_path, "r") as f:
                self.metadatas = json.load(f)
            logger.info(f"✓ Loaded FAISS index with {self.index.ntotal} vectors")
        else:
            self.index = faiss.IndexFlatIP(self.dim)
            self.metadatas = []
            logger.info("✓ Created new FAISS index")

    def add(self, vectors: np.ndarray, metadatas: List[dict]):
        faiss.normalize_L2(vectors)
        self.index.add(vectors.astype('float32'))
        self.metadatas.extend(metadatas)
        self.save()

    def search(self, qvec: np.ndarray, top_k=4):
        if self.index.ntotal == 0:
            return []
        faiss.normalize_L2(qvec)
        D, I = self.index.search(qvec.astype('float32'), top_k)
        results = []
        for scores, idxs in zip(D, I):
            for score, idx in zip(scores, idxs):
                if idx < 0 or idx >= len(self.metadatas):
                    continue
                md = self.metadatas[idx].copy()
                md["score"] = float(score)
                results.append(md)
        return results

    def save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w") as f:
            json.dump(self.metadatas, f)

vector_store = VectorStore(embedding_dim, FAISS_INDEX_PATH, FAISS_META_PATH)

# ---- Helpers ----
def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    tokens = text.split()
    chunks = []
    i = 0
    while i < len(tokens):
        chunk = tokens[i:i+size]
        chunks.append(" ".join(chunk))
        i += size - overlap
    return chunks if chunks else [""]

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        texts = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(texts)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def extract_text_from_csv(file_bytes: bytes) -> str:
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
        return df.to_csv(index=False)
    except Exception as e:
        logger.error(f"CSV extraction error: {e}")
        return ""

def caption_image_bytes(file_bytes: bytes, max_length=64) -> str:
    if not HAS_VISION:
        return "[Image - captioning not available]"
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        pixel_values = vision_processor(images=image, return_tensors="pt").pixel_values
        output_ids = vision_model.generate(pixel_values, max_length=max_length, num_beams=4)
        caption = vision_tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        return caption or "[Image - empty caption]"
    except Exception as e:
        logger.error(f"Image captioning error: {e}")
        return "[Image - error]"

def embed_texts(texts: List[str]) -> np.ndarray:
    embs = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embs.astype('float32')

def call_olama_generate(prompt: str, system: str = "") -> str:
    """Call Ollama locally for generation with timeout"""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = requests_session.post(
            f"{OLAMA_HOST}/api/chat",
            json={
                "model": OLAMA_MODEL,
                "messages": messages,
                "stream": False
            },
            timeout=520
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "No response").strip()
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"Error calling Ollama: {str(e)}"

# ---- Pydantic Models ----
class IngestResponse(BaseModel):
    status: str
    chunks_added: int
    documents_added: int

class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    embedding_time_ms: float
    retrieval_time_ms: float

class HealthResponse(BaseModel):
    status: str
    faiss_vectors: int
    olama_available: bool
    embedding_model: str

# ---- Setup Routes ----
def setup_rag_routes(app: FastAPI):
    """Register RAG endpoints to FastAPI app"""
    
    @app.get("/health", response_model=HealthResponse)
    async def health():
        olama_ok = False
        try:
            r = requests_session.get(f"{OLAMA_HOST}/api/tags", timeout=10)
            olama_ok = r.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
        return HealthResponse(
            status="ok",
            faiss_vectors=vector_store.index.ntotal,
            olama_available=olama_ok,
            embedding_model="all-MiniLM-L6-v2"
        )

    @app.post("/ingest", response_model=IngestResponse)
    async def ingest(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
        """Ingest documents: PDF, CSV, images, text"""
        total_chunks = 0
        total_docs = 0
        db = SessionLocal()
        
        for f in files:
            content = await f.read()
            source = f.filename or str(uuid.uuid4())
            text = ""
            
            # Extract text by file type
            if f.content_type == "application/pdf" or source.lower().endswith(".pdf"):
                text = extract_text_from_pdf(content)
            elif "csv" in f.content_type or source.lower().endswith(".csv"):
                text = extract_text_from_csv(content)
            elif f.content_type.startswith("image/") or any(source.lower().endswith(ext) for ext in [".jpg",".jpeg",".png"]):
                text = caption_image_bytes(content)
            else:
                try:
                    text = content.decode("utf-8")
                except:
                    continue
            
            if not text or len(text) < 10:
                continue
            
            # Chunk and embed
            chunks = chunk_text(text)
            embs = embed_texts(chunks)
            
            # Store in FAISS + DB
            metadatas = []
            for i, chunk in enumerate(chunks):
                doc_id = str(uuid.uuid4())
                metadata = {
                    "source": source,
                    "chunk_index": i,
                    "text": chunk,
                    "doc_id": doc_id
                }
                metadatas.append(metadata)
                
                db_doc = Document(
                    id=doc_id,
                    source=source,
                    chunk_index=i,
                    text=chunk,
                    meta_json=json.dumps(metadata),
                    embedding_dim=embedding_dim
                )
                db.add(db_doc)
                total_chunks += 1
            
            vector_store.add(embs, metadatas)
            total_docs += 1
            db.commit()
        
        db.close()
        return IngestResponse(
            status="ok",
            chunks_added=total_chunks,
            documents_added=total_docs
        )

    @app.post("/query", response_model=QueryResponse)
    async def query(q: str = Form(...), image: Optional[UploadFile] = File(None)):
        """Query: text + optional image → retrieve from FAISS → generate with Ollama"""
        
        # Handle image
        image_caption = ""
        if image and HAS_VISION:
            ib = await image.read()
            image_caption = caption_image_bytes(ib)
        
        # Embed query
        t_emb = time.time()
        q_input = q
        if image_caption:
            q_input = f"{q}\n\n[Image: {image_caption}]"
        q_emb = embed_texts([q_input])
        emb_time = (time.time() - t_emb) * 1000
        
        # Retrieve from FAISS
        t_ret = time.time()
        results = vector_store.search(q_emb, top_k=TOP_K)
        ret_time = (time.time() - t_ret) * 1000
        
        if not results:
            return QueryResponse(
                answer="No documents in knowledge base. Please ingest documents first.",
                sources=[],
                embedding_time_ms=emb_time,
                retrieval_time_ms=ret_time
            )
        
        contexts = [r["text"] for r in results]
        sources = [
            {
                "source": r.get("source"),
                "score": f"{r.get('score', 0):.4f}",
                "chunk": r.get("chunk_index", -1)
            }
            for r in results
        ]
        
        # Build prompt
        system_prompt = (
            "You are a helpful assistant. Answer questions based ONLY on the provided context. "
            "If the context doesn't contain sufficient information, say 'I don't know'. "
            "Be concise and cite sources when possible."
        )
        context_blob = "\n\n---\n\n".join(contexts)
        user_prompt = f"""Context:
{context_blob}

Question: {q}

{f'Image description: {image_caption}' if image_caption else ''}

Answer:"""
        
        # Generate with Ollama
        answer = call_olama_generate(user_prompt, system_prompt)
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            embedding_time_ms=emb_time,
            retrieval_time_ms=ret_time
        )

    @app.get("/documents")
    async def list_documents(limit: int = 50):
        """List ingested documents"""
        db = SessionLocal()
        docs = db.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
        db.close()
        return {
            "count": len(docs),
            "documents": [
                {
                    "id": d.id,
                    "source": d.source,
                    "chunk_index": d.chunk_index,
                    "text_preview": d.text[:100] + "..." if len(d.text) > 100 else d.text,
                    "created_at": d.created_at.isoformat()
                }
                for d in docs
            ]
        }

    @app.delete("/documents/{doc_id}")
    async def delete_document(doc_id: str):
        """Delete a document (note: FAISS index not updated; requires rebuild)"""
        db = SessionLocal()
        db.query(Document).filter(Document.id == doc_id).delete()
        db.commit()
        db.close()
        return {"status": "deleted", "doc_id": doc_id}

    @app.post("/rebuild-index")
    async def rebuild_index():
        """Rebuild FAISS index from database"""
        db = SessionLocal()
        docs = db.query(Document).all()
        
        # Recreate store
        global vector_store
        vector_store = VectorStore(embedding_dim, FAISS_INDEX_PATH, FAISS_META_PATH)
        
        texts = [d.text for d in docs]
        if texts:
            embs = embed_texts(texts)
            metadatas = [
                {
                    "source": d.source,
                    "chunk_index": d.chunk_index,
                    "text": d.text,
                    "doc_id": d.id
                }
                for d in docs
            ]
            vector_store.add(embs, metadatas)
        
        db.close()
        return {"status": "rebuilt", "vectors": vector_store.index.ntotal}
