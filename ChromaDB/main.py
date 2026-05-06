from rag.vector_store import JobApplicationStore

store = JobApplicationStore()
store.add_all_documents("./docs")
print(store.list_documents())