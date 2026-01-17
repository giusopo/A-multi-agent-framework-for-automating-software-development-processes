from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

class KnowledgeBase:
    def __init__(self, vector_dir="chroma", k=6):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        # Carica il DB Chroma già persistente
        self.store = Chroma(
            persist_directory=vector_dir,
            embedding_function=self.embeddings
        )
        self.k = k

    def retrieve(self, query: str):
        """
        Restituisce i chunk più rilevanti come lista di Document
        """
        docs = self.store.similarity_search(query, k=self.k)
        return docs
