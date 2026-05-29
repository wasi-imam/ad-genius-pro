\# 🎯 Ad Genius Pro



> AI-powered ad copy optimization using RAG pipeline, deterministic scoring engine, and a 2-agent critique chain.



\---



\## What is this project?



Ad Genius Pro analyzes your ad copy against real competitor ads and tells you exactly what is missing, why it is weak, and how to fix it — automatically.



You paste your ad. The system:

1\. Finds the most similar competitor ads using vector similarity search

2\. Calculates a viral score (0-100) using a weighted formula

3\. Identifies specific gaps compared to competitors

4\. Rewrites your ad to fix every gap



\---



\## Live Demo



```bash

streamlit run app.py

```



\---



\## Key Engineering Features



\### 1. RAG Pipeline (Retrieval Augmented Generation)

\- 50-entry competitor ad dataset embedded using `sentence-transformers/all-MiniLM-L6-v2`

\- Stored in ChromaDB with cosine similarity search

\- Query-time retrieval in milliseconds

\- Optional: upload competitor PDFs for ingestion



\### 2. Memory-Safe PDF Ingestion

\- Handles files larger than available RAM

\- Streams 5 pages at a time — parse, embed, store, discard

\- Peak RAM usage stays under 50MB regardless of file size

\- Uses `gc.collect()` for explicit memory management



\### 3. Deterministic Scoring Engine

\- Viral score (0-100) using weighted formula

\- LLM extracts variables (hook strength, clarity, sentiment stability)

\- Formula computes final score — not blindly trusting LLM output

\- Validated with Pydantic to prevent silent type errors



\### 4. 2-Agent Critique Chain

\- \*\*Agent 1 (Analyst):\*\* Compares user ad against competitor context, returns structured JSON gaps

\- \*\*Agent 2 (Builder):\*\* Takes gaps as input, rewrites ad with creative temperature

\- Separation of concerns — analyst is analytical (temp=0.2), builder is creative (temp=0.7)



\---



\## Tech Stack



| Layer | Technology |

|---|---|

| UI | Streamlit |

| Vector DB | ChromaDB |

| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |

| LLM | Groq API — LLaMA 3.3 70B |

| PDF Processing | PyMuPDF (fitz) |

| Data Validation | Pydantic |

| PDF Export | FPDF2 |

| Environment | python-dotenv |



\---



\## Project Structure

