# retriever.py
# Purpose: Take user input, search ChromaDB for similar ads,
# return results with similarity scores.
# This file runs on EVERY user request — not just once.

import chromadb
from sentence_transformers import SentenceTransformer

# Global variables — module level pe rakhe hain
_model = None
_collection = None
# underscore (_) — convention for private variables
# matlab: "sirf is file ke andar use karo"
#
# Performance reason:
# Agar har function call pe model load karte:
#   every call: 2-3 seconds loading time
# Global rakhne pe:
#   first call: 2-3 seconds (loads once)
#   every call after: 0.1 seconds (already in RAM)
# Isko "lazy initialization" kehte hain


def _load_resources():
    """
    Load model and ChromaDB connection.
    Only runs on first call — after that globals are already set.
    """
    global _model, _collection
    # global keyword — Python ko batao ki hum
    # global variable modify kar rahe hain
    # naya local variable nahi bana rahe

    if _model is None:
        # sirf pehli baar load karo
        print("Loading retriever resources...")

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        # IMPORTANT: same model jo embedder mein use kiya
        # alag model = alag vectors = comparison meaningless

        client = chromadb.PersistentClient(path="./chroma_db")
        # same path — wahi data read karega jo embedder ne store kiya

        _collection = client.get_collection("competitors")
        # get_collection — existing collection lo
        # get_OR_create nahi — collection pehle se exist karni chahiye
        # nahi mili = embedder pehle nahi chala — clear error aayega


def get_similar_ads(query: str, n_results: int = 5) -> list:
    """
    Find similar competitor ads for a given query.

    Parameters:
        query     : str — user ka product description ya ad text
        n_results : int — kitne results chahiye (default: 5)

    Returns:
        list of dicts — each dict has ad_copy, metadata, similarity score
    """
    # type hints — professional code ka standard
    # query: str = query string hona chahiye
    # n_results: int = 5 — default value 5
    # -> list — function list return karega

    _load_resources()
    # pehli call pe load karega
    # baad ki calls pe skip karega — _model already set hai

    # --- Step 1: Query ko vector mein convert karo ---
    query_vector = _model.encode(query).tolist()
    # same process jo embedder mein tha
    # user ka text → 384 numbers
    # .tolist() — numpy array to Python list

    # --- Step 2: ChromaDB mein search karo ---
    results = _collection.query(
        query_embeddings=[query_vector],
        # list ke andar list — ChromaDB ek saath multiple
        # queries accept karta hai, isliye outer list
        # hum sirf ek query kar rahe hain

        n_results=n_results,
        # kitne similar ads chahiye

        include=["documents", "metadatas", "distances"]
        # documents — original ad_copy text
        # metadatas — brand, platform, sentiment etc.
        # distances — similarity measure (0 = identical, 2 = opposite)
    )
    # ChromaDB andar kya karta hai:
    # 1. query_vector ko har stored vector se compare karta hai
    # 2. cosine distance calculate karta hai
    # 3. sabse similar (chhoti distance) results return karta hai
    # 4. yeh sab milliseconds mein hota hai

    # --- Step 3: Results clean format mein convert karo ---
    similar_ads = []

    for i in range(len(results["documents"][0])):
        # results["documents"] = [[ad1, ad2, ad3, ad4, ad5]]
        # [0] isliye — outer list mein pehli query ke results hain

        distance = results["distances"][0][i]
        # distance — 0 se 2 ke beech
        # 0 = bilkul same, 2 = bilkul opposite

        similarity_score = round(1 - (distance / 2), 3)
        # distance ko similarity mein convert karo
        # distance=0   → similarity=1.0  (perfect match)
        # distance=1   → similarity=0.5  (50% match)
        # distance=2   → similarity=0.0  (no match)
        # round(..., 3) — 3 decimal places

        ad_entry = {
            "ad_copy":          results["documents"][0][i],
            "similarity_score": similarity_score,
            "brand":            results["metadatas"][0][i].get("brand", "Unknown"),
            "product":          results["metadatas"][0][i].get("product", ""),
            "platform":         results["metadatas"][0][i].get("platform", ""),
            "hook":             results["metadatas"][0][i].get("hook", ""),
            "sentiment":        results["metadatas"][0][i].get("sentiment", ""),
            "has_cta":          results["metadatas"][0][i].get("has_cta", "False"),
            "price_mentioned":  results["metadatas"][0][i].get("price_mentioned", "False"),
            "keywords":         results["metadatas"][0][i].get("keywords", "")
            # .get("field", "default") — safely value nikalao
            # agar field missing ho toh default return karo — crash nahi hoga
        }

        similar_ads.append(ad_entry)

    return similar_ads


def format_for_agent(similar_ads: list) -> str:
    """
    Convert similar ads list into readable text for the agent.
    LLM structured text best samajhta hai.
    """
    if not similar_ads:
        return "No similar competitor ads found."

    lines = ["=== TOP COMPETITOR ADS (ranked by similarity) ===\n"]

    for i, ad in enumerate(similar_ads, start=1):
        # enumerate(..., start=1) — 1 se count karo, 0 se nahi
        block = f"""
Competitor {i} | Similarity: {ad['similarity_score']:.0%}
Brand     : {ad['brand']}
Platform  : {ad['platform']}
Hook      : {ad['hook']}
Sentiment : {ad['sentiment']}
Has CTA   : {ad['has_cta']}
Price     : {ad['price_mentioned']}
Keywords  : {ad['keywords']}
Ad Copy   : {ad['ad_copy']}
{'-' * 50}"""
        lines.append(block)

    return "\n".join(lines)