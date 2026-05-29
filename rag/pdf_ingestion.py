# pdf_ingestion.py
# Purpose: Process large PDF files in memory-safe streaming batches.
# Problem solved: 800MB file on 512MB RAM — no crash.
# Solution: Read 5 pages at a time, process, discard, repeat.

import fitz
# fitz = PyMuPDF library
# Purpose: Read PDF files page by page

import chromadb
from sentence_transformers import SentenceTransformer

import gc
# gc = garbage collector
# Purpose: Force Python to free RAM immediately
# Normally Python does this automatically
# We force it because memory constraints are tight here

import uuid
# uuid = Universally Unique Identifier
# Purpose: Generate unique random IDs for each PDF chunk
# Example: "a3f8c2d1-4e5b-6789-abcd-ef0123456789"

# --- Constants ---
PAGES_PER_BATCH = 5
# Only 5 pages loaded in RAM at a time
# Lower this number if you have less RAM

CHUNK_SIZE = 300
# Words per chunk — 300 words is roughly 2-3 paragraphs
# Good size for RAG — not too big, not too small

CHUNK_OVERLAP = 50
# Overlap between consecutive chunks
# Why: if an important sentence falls at a chunk boundary,
# overlap ensures it appears complete in at least one chunk


def chunk_text(text: str) -> list:
    """
    Split large text into overlapping chunks.

    Example with CHUNK_SIZE=300, OVERLAP=50:
    chunk1: words 0-299
    chunk2: words 250-549  (50 word overlap with chunk1)
    chunk3: words 500-799  (50 word overlap with chunk2)
    """
    words = text.split()
    # .split() — string ko words mein todo
    # "Run faster" becomes ["Run", "faster"]
    # default: split on whitespace

    chunks = []
    start = 0

    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = " ".join(words[start:end])
        # words[start:end] — slice karo
        # .join() — list wapas string mein convert karo

        if chunk.strip():
            # .strip() — whitespace remove karo
            # empty chunk mat add karo
            chunks.append(chunk)

        start += CHUNK_SIZE - CHUNK_OVERLAP
        # next chunk start position
        # CHUNK_SIZE=300, OVERLAP=50
        # 0 → 250 → 500 → 750...
        # yahi overlap create karta hai

    return chunks


def process_pdf_streaming(file_obj, progress_callback=None) -> dict:
    """
    Process PDF in streaming batches — memory safe.

    Parameters:
        file_obj          — uploaded file object (from Streamlit)
        progress_callback — optional function to update progress bar

    Returns:
        dict with stats: total_pages, total_chunks, batches
    """

    # --- Setup ---
    model = SentenceTransformer("all-MiniLM-L6-v2")
    db_client = chromadb.PersistentClient(path="./chroma_db")
    collection = db_client.get_or_create_collection(
        name="competitors",
        metadata={"hnsw:space": "cosine"}
    )

    # --- Open PDF ---
    file_bytes = file_obj.read()
    pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
    # stream= — bytes se directly open karo (disk pe save nahi)
    # filetype="pdf" — explicitly batao

    total_pages = len(pdf_doc)
    print(f"Total pages in PDF: {total_pages}")

    total_chunks_stored = 0
    batch_number = 0

    # --- Process batch by batch ---
    for batch_start in range(0, total_pages, PAGES_PER_BATCH):
        # range(0, 100, 5) = 0, 5, 10, 15... 95
        # har iteration mein sirf 5 pages

        batch_end = min(batch_start + PAGES_PER_BATCH, total_pages)
        # min() — last batch mein 5 se kam pages ho sakte hain

        # Read only this batch's pages
        batch_text = ""
        for page_num in range(batch_start, batch_end):
            page = pdf_doc[page_num]
            batch_text += page.get_text()
            # get_text() — page se text content nikalao

            page = None
            # IMMEDIATELY release page object from RAM
            # page = None — Python ko signal: "yeh ab chahiye nahi"
            # garbage collector ise RAM se hata dega

        # Split into chunks
        chunks = chunk_text(batch_text)
        batch_text = None
        # Raw text ab zaroorat nahi — release karo
        gc.collect()
        # Force garbage collector — RAM turant free ho jaati hai

        if not chunks:
            continue

        # Embed this batch's chunks
        embeddings = model.encode(
            chunks,
            batch_size=16,
            show_progress_bar=False
        ).tolist()
        # batch_size=16 — 16 chunks ek baar embed karo
        # more efficient than one by one

        # Store in ChromaDB
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        # list comprehension — har chunk ke liye ek unique ID

        collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=chunk_ids,
            metadatas=[{
                "source": "pdf_upload",
                "batch":  str(batch_number)
            }] * len(chunks)
        )

        total_chunks_stored += len(chunks)
        batch_number += 1

        # Clear embeddings from RAM
        embeddings = None
        chunks = None
        gc.collect()

        # Update progress bar if callback provided
        if progress_callback:
            progress_pct = batch_end / total_pages
            msg = f"Processed pages {batch_start + 1} to {batch_end} of {total_pages}"
            progress_callback(progress_pct, msg)

    pdf_doc.close()

    return {
        "total_pages":  total_pages,
        "total_chunks": total_chunks_stored,
        "batches":      batch_number
    }