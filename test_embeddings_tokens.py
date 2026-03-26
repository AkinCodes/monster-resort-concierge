#!/usr/bin/env python3
"""
Destruction Lab: Embeddings & Token Explorer
=============================================
Interactive script to experiment with:
  1. Raw embeddings — see the actual vectors behind text
  2. Similarity scores — compare how close/far texts are in embedding space
  3. RAG retrieval — see what the knowledge base returns for any query
  4. LLM token usage — measure prompt/completion tokens per request
  5. Token cost scaling — watch how costs grow with input size

Usage:
  uv run python test_embeddings_tokens.py
"""

import json
import sys
import numpy as np
from sentence_transformers import SentenceTransformer

# --- PART 1: EMBEDDINGS ---

print("=" * 70)
print("PART 1: RAW EMBEDDINGS")
print("=" * 70)

model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"\nModel: all-MiniLM-L6-v2")
print(f"Embedding dimensions: {model.get_sentence_embedding_dimension()}\n")

# Embed a single text
sample = "Vampire Manor offers luxurious coffin suites"
embedding = model.encode(sample)

print(f"Text: \"{sample}\"")
print(f"Vector shape: {embedding.shape}")
print(f"First 10 values: {embedding[:10].round(4).tolist()}")
print(f"Min: {embedding.min():.4f}  Max: {embedding.max():.4f}  Mean: {embedding.mean():.4f}")

# --- PART 2: SIMILARITY SCORES ---

print("\n" + "=" * 70)
print("PART 2: SIMILARITY SCORES")
print("=" * 70)

texts = [
    "Vampire Manor offers luxurious coffin suites",           # A: Resort text
    "The Eternal Night Inn has elegant resting chambers",      # B: Similar meaning
    "Book a room at the monster hotel",                        # C: Related topic
    "The weather in Tokyo is sunny today",                     # D: Unrelated
    "SELECT * FROM bookings WHERE id = 1",                    # E: SQL injection
    "Justice League Sanctuary orbiting Earth",                 # F: DC Comics (poisoning)
]

labels = ["A: Resort text", "B: Similar meaning", "C: Related topic",
          "D: Unrelated", "E: SQL injection", "F: DC poisoning"]

embeddings = model.encode(texts)

# Compute cosine similarity matrix
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print("\nTexts:")
for label, text in zip(labels, texts):
    print(f"  {label}: \"{text}\"")

print("\nSimilarity Matrix (cosine similarity):")
print(f"{'':>20}", end="")
for i in range(len(texts)):
    print(f"  {chr(65+i):>6}", end="")
print()

for i in range(len(texts)):
    print(f"  {chr(65+i)}: {labels[i]:<16}", end="")
    for j in range(len(texts)):
        sim = cosine_sim(embeddings[i], embeddings[j])
        print(f"  {sim:>6.3f}", end="")
    print()

print("\nKey observations:")
a_b = cosine_sim(embeddings[0], embeddings[1])
a_d = cosine_sim(embeddings[0], embeddings[3])
a_f = cosine_sim(embeddings[0], embeddings[5])
print(f"  A↔B (similar hotel texts):  {a_b:.3f}  — HIGH (same domain)")
print(f"  A↔D (hotel vs weather):     {a_d:.3f}  — LOW (different domain)")
print(f"  A↔F (hotel vs DC Comics):   {a_f:.3f}  — {'MEDIUM' if a_f > 0.3 else 'LOW'} (poison detection signal)")

# --- PART 3: RAG RETRIEVAL ---

print("\n" + "=" * 70)
print("PART 3: RAG RETRIEVAL — What does the knowledge base return?")
print("=" * 70)

try:
    from app.records_room.rag import VectorRAG
except ImportError:
    from app.rag import VectorRAG

rag = VectorRAG(
    persist_dir="./.rag_store",
    collection="monster_resort_knowledge",
)

queries = [
    "Vampire Manor amenities",
    "quantum physics experiments",
    "Justice League Sanctuary",
    "DROP TABLE bookings",
]

for query in queries:
    results = rag.search(query, k=3)
    hits = results.get("results", [])
    print(f"\nQuery: \"{query}\"")
    if not hits:
        print("  No results found.")
    for i, r in enumerate(hits):
        score = r["score"]
        text_preview = r["text"][:80].replace("\n", " ")
        source = r.get("meta", {}).get("source", "unknown")
        print(f"  [{i+1}] Score: {score:.4f} | Source: {source}")
        print(f"      \"{text_preview}...\"")

# --- PART 4: EMBEDDING DISTANCE FROM CENTROID (Defense 5 visualization) ---

print("\n" + "=" * 70)
print("PART 4: ANOMALY DETECTION — Distance from knowledge base centroid")
print("=" * 70)

existing = rag.collection.get(include=["embeddings"], limit=500)
existing_embs = np.array(existing.get("embeddings", []))

if len(existing_embs) > 0:
    centroid = existing_embs.mean(axis=0)
    distances = np.linalg.norm(existing_embs - centroid, axis=1)
    mean_dist = distances.mean()
    std_dist = distances.std()

    print(f"\nKnowledge base stats:")
    print(f"  Documents: {len(existing_embs)}")
    print(f"  Mean distance from centroid: {mean_dist:.4f}")
    print(f"  Std deviation: {std_dist:.4f}")
    print(f"  Anomaly threshold (3σ): {mean_dist + 3 * std_dist:.4f}")

    test_texts = [
        "Vampire Manor coffin suites with satin lining",
        "The Werewolf Lodge offers moonlit hiking trails",
        "Justice League Sanctuary orbiting Earth in the Watchtower",
        "The mitochondria is the powerhouse of the cell",
        "SELECT * FROM users WHERE 1=1 --",
    ]

    test_embs = model.encode(test_texts)
    test_distances = np.linalg.norm(test_embs - centroid, axis=1)

    print(f"\nTest texts — distance from centroid:")
    threshold = mean_dist + 3 * std_dist
    for text, dist in zip(test_texts, test_distances):
        flag = "⚠️  ANOMALY" if dist > threshold else "✅ Normal"
        print(f"  {flag} | dist={dist:.4f} | \"{text[:60]}\"")

# --- PART 5: LLM TOKEN USAGE ---

print("\n" + "=" * 70)
print("PART 5: LLM TOKEN USAGE")
print("=" * 70)

import httpx

API_KEY = os.environ.get("MRC_API_KEY", "your-api-key-here")
BASE_URL = "http://localhost:8000"

test_messages = [
    ("Short query", "Hi"),
    ("Medium query", "What amenities does Vampire Manor offer?"),
    ("Long query", "I would like to book a room at Vampire Manor for Count Dracula, checking in on March 28th and checking out on March 30th. Please provide the Coffin Suite with satin lining and ensure there are blackout curtains. Also, what dining options are available?"),
    ("Booking request", "Book a room at Vampire Manor for Dracula, checking in tonight"),
]

print(f"\nSending requests to {BASE_URL}/chat ...")
print(f"(Make sure the server is running!)\n")

for label, msg in test_messages:
    try:
        resp = httpx.post(
            f"{BASE_URL}/chat",
            json={"message": msg},
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            timeout=30,
        )
        data = resp.json()

        reply = data.get("reply", data.get("message", ""))
        tools = data.get("tools_used", [])
        provider = data.get("provider", "unknown")

        print(f"[{label}]")
        print(f"  Message: \"{msg[:60]}{'...' if len(msg) > 60 else ''}\"")
        print(f"  Reply length: {len(reply)} chars")
        print(f"  Provider: {provider}")
        print(f"  Tools used: {[t['tool'] for t in tools] if tools else 'none'}")

        # Token usage isn't in the /chat response yet, so estimate
        # Rough estimate: 1 token ≈ 4 chars for English text
        est_input = len(msg) // 4
        est_output = len(reply) // 4
        print(f"  Estimated tokens — input: ~{est_input}, output: ~{est_output}, total: ~{est_input + est_output}")
        print()

    except httpx.ConnectError:
        print(f"[{label}] ❌ Server not running at {BASE_URL}")
        print(f"  Start it with: lsof -t -i:8000 | xargs kill -9 2>/dev/null || true && uv run uvicorn app.main:app --reload")
        break
    except Exception as e:
        print(f"[{label}] ❌ Error: {e}")

print("=" * 70)
print("EXPERIMENT COMPLETE")
print("=" * 70)
