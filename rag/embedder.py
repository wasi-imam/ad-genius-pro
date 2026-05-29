# embedder.py
# Purpose: Read competitors.json, convert each ad_copy to a vector,
# and store everything in ChromaDB.
# Run this file ONLY ONCE during project setup.

import json
# json — Python built-in library
# Purpose: JSON file ko Python list mein convert karna

import chromadb
# chromadb — hamara vector database
# Purpose: vectors store karna aur similarity search karna

from sentence_transformers import SentenceTransformer
# SentenceTransformer — ML library
# Purpose: text ko numbers (vectors) mein convert karna


def build_vector_db():
    # Yeh function poora kaam karta hai
    # app.py se bhi call kar sakte hain agar zaroorat pade

    # --- Step 1: ChromaDB client banao ---
    client = chromadb.PersistentClient(path="./chroma_db")
    # PersistentClient — data disk pe save hoga, RAM mein nahi
    # path="./chroma_db" — project folder mein chroma_db/ folder banega
    # agar sirf Client() use karte — program band hone pe data delete ho jaata

    # --- Step 2: Collection banao ---
    collection = client.get_or_create_collection(
        name="competitors",
        metadata={"hnsw:space": "cosine"}
    )
    # collection — database ke andar ek table jaisi cheez
    # get_or_create — agar exist kare toh wahi use karo, nahi toh naya banao
    # hnsw:space = "cosine" — similarity measure karne ka method
    # cosine similarity: do vectors ke beech angle measure karta hai
    # similar text = chhota angle = score 0 se 1 ke beech

    # --- Step 3: Embedding model load karo ---
    print("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    # all-MiniLM-L6-v2 — pre-trained model
    # pehli baar internet se download hoga (~90MB)
    # baad mein cache se load hoga — fast
    # yeh model har sentence ko 384 numbers ki list mein convert karta hai

    # --- Step 4: JSON file padhho ---
    print("Reading dataset...")
    with open("data/competitors.json", "r", encoding="utf-8") as f:
        ads = json.load(f)
    # with open(...) — file safely kholo, kaam hone pe auto close
    # "r" = read mode
    # encoding="utf-8" — special characters handle karna
    # json.load(f) — JSON text ko Python list mein convert karo
    # ads = 50 dictionaries ki list, har dictionary ek ad hai

    print(f"Total ads loaded: {len(ads)}")

    # --- Step 5: Lists prepare karo ---
    documents = []
    # ad_copy text — yahi actually embed hoga

    embeddings = []
    # vectors — 384 numbers ki lists

    ids = []
    # unique IDs — ChromaDB ko chahiye records track karne ke liye

    metadatas = []
    # extra info — brand, platform, sentiment etc.

    print("Generating embeddings... this may take a minute.")

    for i, ad in enumerate(ads):
        # enumerate — index aur item dono ek saath milte hain
        # i = 0,1,2... (position number)
        # ad = ek dictionary {"id": "ad_001", "brand": "Nike"...}

        # ad_copy nikaloo — yahi vector banega
        ad_copy_text = ad["ad_copy"]

        # vector banao
        vector = model.encode(ad_copy_text)
        # model.encode() — text ko 384 numbers mein convert karta hai
        # input:  "Run faster. Push harder."
        # output: [0.23, -0.11, 0.87, ...] (384 numbers)
        # similar sentences ke vectors similar hote hain — yahi magic hai

        vector_as_list = vector.tolist()
        # .tolist() — numpy array ko Python list mein convert karo
        # ChromaDB ko Python list chahiye, numpy array nahi

        # metadata prepare karo
        metadata = {
            "brand":           ad["brand"],
            "product":         ad["product"],
            "platform":        ad["platform"],
            "hook":            ad["hook"],
            "sentiment":       ad["sentiment"],
            "has_cta":         str(ad["has_cta"]),
            # str() isliye — ChromaDB boolean directly store nahi karta
            "price_mentioned": str(ad["price_mentioned"]),
            "length_words":    ad["length_words"],
            "keywords":        ", ".join(ad["keywords"])
            # list ko string mein convert karo
            # ["speed", "run"] becomes "speed, run"
        }

        documents.append(ad_copy_text)
        embeddings.append(vector_as_list)
        ids.append(ad["id"])
        metadatas.append(metadata)

        print(f"  [{i+1}/50] {ad['brand']} — embedded successfully")

    # --- Step 6: ChromaDB mein store karo ---
    print("\nStoring in ChromaDB...")
    collection.add(
        documents=documents,
        # original text — search result mein wapas milega

        embeddings=embeddings,
        # actual vectors — similarity search ke liye

        ids=ids,
        # unique identifiers

        metadatas=metadatas
        # extra info jo retriever return karega
    )

    print(f"\nDone! {len(ads)} ads stored in ChromaDB.")
    print("Database saved at: ./chroma_db/")


if __name__ == "__main__":
    # Yeh block sirf tab chalega jab file directly run ki jaye
    # python rag/embedder.py — chalega
    # koi aur file import kare — nahi chalega
    build_vector_db()