import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from get_embedding_function import get_embedding_function

DATA_DIR = "data/step_name"
CHROMA_PATH = "chroma/step_name"

def sanitize_metadata(metadata: dict) -> dict:
    """
    Pulisce il metadata per Chroma:
    - Rimuove chiavi vuote o None
    - Rimuove valori None
    - Converte valori non primitivi in stringhe
    """
    clean = {}
    for k, v in metadata.items():
        # ignora chiavi vuote o None
        if not k or v is None:
            continue
        # valori primitivi
        elif isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            try:
                clean[k] = str(v)
            except Exception:
                clean[k] = repr(v)
    return clean

def load_pdfs():
    documents = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(DATA_DIR, filename))
            documents.extend(loader.load())
    return documents

def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,       
        chunk_overlap=100        
    )
    return splitter.split_documents(documents)

def calculate_chunk_ids(chunks):
    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"

        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        chunk.metadata["id"] = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

    return chunks


def main():
    documents = load_pdfs()
    chunks = split_documents(documents)
    chunks = calculate_chunk_ids(chunks)

    db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=get_embedding_function()
    )

    existing_items = db.get(include=[])
    existing_ids = set(existing_items["ids"])
    print(f"Documenti già nel DB: {len(existing_ids)}")

    new_chunks = [
        chunk for chunk in chunks
        if chunk.metadata["id"] not in existing_ids
    ]

    for i, chunk in enumerate(new_chunks):
        try:
            chunk.metadata = sanitize_metadata(chunk.metadata)
        except Exception as e:
            print(f"Errore metadata chunk index {i}: {chunk.metadata} -> {e}")

    if new_chunks:
        print(f"Aggiungo {len(new_chunks)} nuovi chunk")
        db.add_documents(
            new_chunks,
            ids=[chunk.metadata["id"] for chunk in new_chunks]
        )
    else:
        print("Nessun nuovo documento da aggiungere")


if __name__ == "__main__":
    main()
