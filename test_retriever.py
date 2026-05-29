# test_retriever.py
# Purpose: Verify that ChromaDB is working and returning similar ads correctly.
# Delete this file after testing — it is not part of the final project.

from rag.retriever import get_similar_ads, format_for_agent

print("=" * 50)
print("TEST 1: Running shoes query")
print("=" * 50)

results = get_similar_ads("affordable running shoes for athletes", n_results=3)

print(f"Results found: {len(results)}\n")
for ad in results:
    print(f"Brand      : {ad['brand']}")
    print(f"Similarity : {ad['similarity_score']:.0%}")
    print(f"Platform   : {ad['platform']}")
    print(f"Ad Copy    : {ad['ad_copy'][:80]}...")
    print("-" * 40)

print("\n")
print("=" * 50)
print("TEST 2: Skincare product query")
print("=" * 50)

results2 = get_similar_ads("natural face wash for glowing skin", n_results=3)

print(f"Results found: {len(results2)}\n")
for ad in results2:
    print(f"Brand      : {ad['brand']}")
    print(f"Similarity : {ad['similarity_score']:.0%}")
    print(f"Ad Copy    : {ad['ad_copy'][:80]}...")
    print("-" * 40)

print("\n")
print("=" * 50)
print("TEST 3: Agent format output")
print("=" * 50)
print(format_for_agent(results2))