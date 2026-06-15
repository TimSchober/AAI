#!/usr/bin/env python3
"""
Health Check Script: Prüfe Ollama und API Status
Verwendung: python3 health_check.py
"""

import sys
import time

def check_ollama():
    """Prüfe ob Ollama läuft"""
    print("\n🔍 Prüfe Ollama...")
    try:
        import requests
        from config import OLAMA_HOST, OLAMA_MODEL
        
        response = requests.get(f"{OLAMA_HOST}/api/tags", timeout=5)
        
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            print(f"✅ Ollama läuft auf {OLAMA_HOST}")
            print(f"   Verfügbare Modelle: {model_names}")
            
            if OLAMA_MODEL in model_names:
                print(f"   ✅ Model '{OLAMA_MODEL}' geladen")
                return True
            else:
                print(f"   ⚠️  Model '{OLAMA_MODEL}' NICHT geladen")
                print(f"   Fix: ollama pull {OLAMA_MODEL}")
                return False
        else:
            print(f"❌ Ollama antwortet mit Status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Kann nicht zu Ollama verbinden ({OLAMA_HOST})")
        print("   Fix: ollama serve (in separatem Terminal)")
        return False
    except Exception as e:
        print(f"❌ Ollama-Fehler: {e}")
        return False

def check_api():
    """Prüfe ob RAG API läuft"""
    print("\n🔍 Prüfe RAG API...")
    try:
        import requests
        
        response = requests.get("http://localhost:8000/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ RAG API läuft auf http://localhost:8000")
            print(f"   Status: {data.get('status')}")
            print(f"   FAISS Vectors: {data.get('faiss_vectors', 0)}")
            print(f"   Ollama verfügbar: {data.get('olama_available')}")
            return True
        else:
            print(f"❌ API antwortet mit Status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Kann nicht zu API verbinden (http://localhost:8000)")
        print("   Fix: python main.py (in separatem Terminal)")
        return False
    except Exception as e:
        print(f"❌ API-Fehler: {e}")
        return False

def main():
    print("╔════════════════════════════════════════╗")
    print("║  Health Check: Ollama + RAG API        ║")
    print("╚════════════════════════════════════════╝")
    
    ollama_ok = check_ollama()
    api_ok = check_api()
    
    print("\n" + "="*40)
    print("ZUSAMMENFASSUNG:")
    print("="*40)
    print(f"Ollama:  {'✅ OK' if ollama_ok else '❌ NICHT AKTIV'}")
    print(f"RAG API: {'✅ OK' if api_ok else '❌ NICHT AKTIV'}")
    print("="*40)
    
    if ollama_ok and api_ok:
        print("\n✨ Alles läuft! Du kannst die API nutzen.")
        print("   - Swagger UI: http://localhost:8000/docs")
        print("   - Health: http://localhost:8000/health")
    elif ollama_ok and not api_ok:
        print("\n⚠️  Ollama läuft, aber API nicht.")
        print("   Starte API: python main.py")
    elif not ollama_ok and api_ok:
        print("\n⚠️  API läuft, aber Ollama nicht.")
        print("   Starte Ollama: ollama serve")
    else:
        print("\n❌ Weder Ollama noch API laufen.")
        print("   Terminal 1: ollama serve")
        print("   Terminal 2: python main.py")
    
    return ollama_ok and api_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
