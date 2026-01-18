import argparse
import shutil
from pathlib import Path

from langchain.document_loaders.pdf import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from langchain.vectorstores.chroma import Chroma

from get_embedding_function import get_embedding_function

# Paths to your documents
ADD_DOCS_DIR = Path("docs/add")  # materiale per ADD
ARCH_SEL_DOCS_DIR = Path("docs/arch_selection")  # materiale per scelta architettura
COMP_DOCS_DIR = Path("docs/component_dec")  # materiale per la scomposizione in componenti

# Persistence directories
ADD_DB_DIR = Path("chroma/chroma_add")
ARCH_SEL_DB_DIR = Path("chroma/chroma_arch_selection")
COMP_DB_DIR = Path("chroma/chroma_component")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and rebuild the Chroma databases"
    )
    args = parser.parse_args()

    if args.reset:
        print("✨ Clearing databases")
        clear_database(ADD_DB_DIR)
        clear_database(ARCH_SEL_DB_DIR)
        clear_database(COMP_DB_DIR)

    # Popoliamo il DB per ADD
    print("📄 Loading ADD documents...")
    add_docs = load_documents(ADD_DOCS_DIR)
    print(f"📑 Loaded {len(add_docs)} pages for ADD")
    add_chunks = split_documents(add_docs, db_type="ADD")
    print(f"🧩 Created {len(add_chunks)} chunks for ADD")
    add_to_chroma(add_chunks, ADD_DB_DIR)

    # Popoliamo il DB per Architettura
    print("📄 Loading Architecture Selection documents...")
    arch_docs = load_documents(ARCH_SEL_DOCS_DIR)
    print(f"📑 Loaded {len(arch_docs)} pages for Architecture Selection")
    arch_chunks = split_documents(arch_docs, db_type="ARCH")
    print(f"🧩 Created {len(arch_chunks)} chunks for Architecture Selection")
    add_to_chroma(arch_chunks, ARCH_SEL_DB_DIR)

    # Popoliamo il DB per Component Design
    print("📄 Loading Component Design documents...")
    comp_docs = load_documents(COMP_DOCS_DIR)
    print(f"📑 Loaded {len(comp_docs)} pages for Component Design")
    comp_chunks = split_documents(comp_docs, db_type="COMP")
    print(f"🧩 Created {len(comp_chunks)} chunks for Component Design")
    add_to_chroma(comp_chunks, COMP_DB_DIR)

    print("✅ Database population complete")


def load_documents(path: Path) -> list[Document]:
    loader = PyPDFDirectoryLoader(str(path))
    return loader.load()


def split_documents(documents: list[Document], db_type: str) -> list[Document]:
    """
    Chunk documents differently based on the target DB:
    - ADD: più piccoli, dettaglio requisiti e functional drivers
    - ARCH: più grandi, pattern architetturali, QA, rischi
    - COMP: medi, design dei componenti e interfacce
    """
    if db_type == "ADD":
        chunk_size = 900
        chunk_overlap = 80
    elif db_type == "ARCH":
        chunk_size = 1050
        chunk_overlap = 100
    elif db_type == "COMP":
        chunk_size = 600
        chunk_overlap = 90
    else:
        raise ValueError(f"Unknown db_type: {db_type}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " "],
        length_function=len,
    )

    return splitter.split_documents(documents)


def add_to_chroma(chunks: list[Document], chroma_path: Path):
    db = Chroma(
        persist_directory=str(chroma_path),
        embedding_function=get_embedding_function(),
    )

    # Optional sanity check
    try:
        existing_count = db._collection.count()
        print(f"📦 Existing chunks in DB: {existing_count}")
    except Exception:
        print("📦 New database detected")

    db.add_documents(chunks)
    db.persist()
    print(f"➕ Added {len(chunks)} chunks to database at {chroma_path}")


def clear_database(chroma_path: Path):
    if chroma_path.exists():
        shutil.rmtree(chroma_path)
        print(f"🗑️ Chroma directory {chroma_path} removed")


if __name__ == "__main__":
    main()
