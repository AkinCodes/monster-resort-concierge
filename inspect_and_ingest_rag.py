#!/usr/bin/env python3
"""
Inspect and ingest knowledge into VectorRAG for Monster Resort Concierge.
Run with: uv run python inspect_and_ingest_rag.py
"""

import sys
from pathlib import Path

try:
    from app.rag import VectorRAG
    from app.config import get_settings
except ImportError as e:
    print("ERROR: Could not import app modules.")
    print("Make sure you're in the project folder and venv is active:")
    print("  source .venv/bin/activate")
    print(f"Import error: {e}")
    sys.exit(1)


def main():
    print("=== Monster Resort RAG Inspector & Ingester ===\n")

    # Load settings
    try:
        settings = get_settings()
        print(f"Settings loaded: persist_dir={settings.rag_persist_dir}")
        print(f"Collection: {settings.rag_collection}")
    except Exception as e:
        print(f"Failed to load settings: {e}")
        sys.exit(1)

    # Try to initialize VectorRAG - try different argument styles
    print("Initializing VectorRAG...")
    rag = None
    try:
        # Most common pattern: persist_dir, collection_name, embedding_model
        rag = VectorRAG(
            persist_dir=settings.rag_persist_dir,
            collection_name=settings.rag_collection,  # try this first
            embedding_model=getattr(settings, "embedding_model", "all-MiniLM-L6-v2"),
        )
        print("Initialized with collection_name keyword.")
    except TypeError as e:
        print(f"collection_name failed: {e}")
        try:
            # Fallback: positional or different name
            rag = VectorRAG(
                settings.rag_persist_dir,
                settings.rag_collection,  # positional
                embedding_model=getattr(
                    settings, "embedding_model", "all-MiniLM-L6-v2"
                ),
            )
            print("Initialized with positional collection argument.")
        except TypeError as e2:
            print(f"Positional also failed: {e2}")
            print("\nPlease check app/rag.py __init__ signature and update the call.")
            sys.exit(1)

    if rag is None:
        print("Failed to create VectorRAG instance.")
        sys.exit(1)

    # Show current state
    try:
        count = rag.collection.count()
        print(f"Current number of documents in collection: {count}")
    except AttributeError:
        print(
            "Error: rag.collection.count() not available. Check VectorRAG implementation."
        )

    if count == 0:
        print("\nCollection is empty. Ingesting knowledge now...")

        documents = [
            {
                "source": "amenities.txt",
                "text": """Official Monster Resort Lodgings:
1. The Mummy Resort & Tomb-Service (Sarcophagus Suites)
2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites)
3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites)
4. Vampire Manor: Eternal Night Inn (Coffin Suites)
5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites)
6. Ghostly B&B: Spectral Stay (Floating Spectral Suites)

Amenities:
- Blood Bar (Vampire Manor)
- Afterlife Bistro (Mummy Resort)
- Primal Buffet (Werewolf Lodge)
- Lightning Spa (Castle Frankenstein)""",
            },
            {
                "source": "checkin_checkout.txt",
                "text": """Check-in is from 3:00 PM. Early check-in is available based on lair readiness.
Checkout is by 11:00 AM. Late checkout may incur a small broomstick fee.
For nocturnal guests, we can arrange "moonlight arrival" with prior notice.""",
            },
        ]

        texts = [doc["text"] for doc in documents]
        sources = [doc["source"] for doc in documents]

        print(f"Ingesting {len(texts)} documents...")
        try:
            rag.ingest_texts(
                texts, source="manual_test"
            )  # adjust if your method needs metadatas
            print("Ingestion complete.")
        except Exception as e:
            print(f"Ingestion failed: {e}")
            sys.exit(1)

        count = rag.collection.count()
        print(f"New number of documents: {count}")

    # Test searches
    print("\n=== Test Searches ===")
    queries = ["spa services", "check-in time", "Werewolf Lodge", "Lightning Spa"]

    for q in queries:
        print(f"\nQuery: {q}")
        try:
            results = rag.search(q)
            if results:
                print(f"Found {len(results)} result(s):")
                for i, r in enumerate(results, 1):
                    text_preview = (
                        r.get("text", str(r))[:150] + "..."
                        if len(str(r)) > 150
                        else str(r)
                    )
                    print(f"  {i}. {text_preview}")
            else:
                print("No results found.")
        except Exception as e:
            print(f"Search failed: {e}")

    print("\nDone. Your agent should now use real knowledge from these documents.")


if __name__ == "__main__":
    main()









# Fantastic — the script ran successfully this time!
# Key takeaways from the output:

# VectorRAG initialized correctly using the positional argument style (good catch — your class takes persist_dir, collection, ... not collection_name).
# Current number of documents: 38 → your knowledge base is not empty! There's already data in the Chroma collection (likely from previous ingestion attempts or auto-ingest in your app).
# All test searches returned results (3 each time):
# Every query ("spa services", "check-in time", "Werewolf Lodge", "Lightning Spa") found matches.
# The output format Found 3 result(s): 1. ok 2. query 3. results means your rag.search() method is returning a dict like {"ok": True, "query": "...", "results": [...]} — that's why you see those three keys printed.


# This is excellent news — your RAG pipeline is working and has 38 documents indexed. The agent should now be able to pull real knowledge instead of hallucinating/falling back.
# Why the Agent Was Still Giving Fallback Replies Earlier
# Even with 38 documents, you were seeing generic LLM responses. Possible reasons (now that we know the DB has data):

# The rag.search() results are not being used properly in the agent logic.
# Your logs show successful tool calls (search_amenities_called), but the final response is still LLM-generated ("Alas, I must inform you...").
# Likely the agent is not incorporating the search results into its prompt/context, or it's deciding to ignore them.

# Relevance threshold too high — matches exist, but scores are low → agent falls back.
# Prompt engineering issue — the system prompt tells the LLM to prefer its own knowledge over tool results.

# Quick Next Steps to Make Agent Use Real Knowledge

# Inspect what rag.search("spa services") actually returns
# Run this in the same activated venv:Bashuv run python -c "
# from app.rag import VectorRAG
# from app.config import get_settings
# settings = get_settings()
# rag = VectorRAG(settings.rag_persist_dir, settings.rag_collection)
# print(rag.search('spa services'))
# "Paste the full output here — we'll see the actual text chunks and scores.
# Check your agent logic (likely in main.py or wherever _agent_reply lives)
# Look for where it handles tool results. It should do something like:Pythonif tool_result.get("ok") and tool_result.get("results"):
#     context = "\n".join([r["text"] for r in tool_result["results"]])
#     prompt = f"Use this information: {context}\n\nUser: {user_text}"
#     # then call LLM with promptIf it's not appending search results to the prompt → that's why fallback happens.
# Temporary debug in chat
# Temporarily modify the agent response to dump raw tool output:Python# In _agent_reply or wherever final response is built
# if tool_calls:
#     print("RAW TOOL RESULT:", tool_result)  # debug
#     final_msg = f"Tool returned: {json.dumps(tool_result)}\n\n{response}"Restart server → ask "spa services" → check server logs for the raw result.
# Optional: Force ingestion of your exact texts again
# If search returns weird data, re-ingest cleanly:Bashuv run python -c "
# from app.rag import VectorRAG
# from app.config import get_settings
# settings = get_settings()
# rag = VectorRAG(settings.rag_persist_dir, settings.rag_collection)
# texts = [
#     'Check-in is from 3:00 PM. Early check-in is available based on lair readiness. Checkout is by 11:00 AM. Late checkout may incur a small broomstick fee. For nocturnal guests, we can arrange \"moonlight arrival\" with prior notice.',
#     'Official Monster Resort Lodgings: 1. The Mummy Resort & Tomb-Service (Sarcophagus Suites) 2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites) 3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites) 4. Vampire Manor: Eternal Night Inn (Coffin Suites) 5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites) 6. Ghostly B&B: Spectral Stay (Floating Spectral Suites) Amenities: - Blood Bar (Vampire Manor) - Afterlife Bistro (Mummy Resort) - Primal Buffet (Werewolf Lodge) - Lightning Spa (Castle Frankenstein)'
# ]
# rag.ingest_texts(texts, source='manual')
# print('Ingested. New count:', rag.collection.count())
# print(rag.search('Lightning Spa'))
# "Then re-test chat.

# Summary

# RAG is working (38 docs, searches return results).
# Agent isn't using search output → likely prompt/logic bug.
# Run the uv run python -c ... snippet above for rag.search('spa services') — paste output.
# We'll fix the agent to include real results next.

# Let me know the search output — we'll make the agent answer "Lightning Spa at Castle Frankenstein" instead of fallback poetry! 🚀12.9sFastakin.olusanya@U-SH-HO-MAC211-5 monster-resort-concierge % uv run python -c "
# from app.rag import VectorRAG
# from app.config import get_settings
# settings = get_settings()
# rag = VectorRAG(settings.rag_persist_dir, settings.rag_collection)
# print(rag.search('spa services'))
# "
# 2026-01-30 11:18:40,553 - monster_resort - INFO - [PROFILE] search took 0.0691s
# {'ok': True, 'query': 'spa services', 'results': [{'text': 'Official Monster Resort Lodgings:\n1. The Mummy Resort & Tomb-Service (Sarcophagus Suites)\n2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites)\n3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites)\n4. Vampire Manor: Eternal Night Inn (Coffin Suites)\n5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites)\n6. Ghostly B&B: Spectral Stay (Floating Spectral Suites)\n\nAmenities:\n- Blood Bar (Vampire Manor)\n- Afterlife Bistro (Mummy Resort)\n- Primal Buffet (Werewolf Lodge)\n- Lightning Spa (Castle Frankenstein)\n', 'meta': {'source': 'folder:/Users/akin.olusanya/Desktop/monster-resort-concierge/data/knowledge'}, 'score': 1.483931541336324}, {'text': 'Official Monster Resort Lodgings:\n1. The Mummy Resort & Tomb-Service (Sarcophagus Suites)\n2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites)\n3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites)\n4. Vampire Manor: Eternal Night Inn (Coffin Suites)\n5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites)\n6. Ghostly B&B: Spectral Stay (Floating Spectral Suites)\n\nAmenities:\n- Blood Bar (Vampire Manor)\n- Afterlife Bistro (Mummy Resort)\n- Primal Buffet (Werewolf Lodge)\n- Lightning Spa (Castle Frankenstein)\n', 'meta': {'source': 'folder:/Users/akin.olusanya/Desktop/monster-resort-concierge/data/knowledge'}, 'score': 1.483931541336324}, {'text': 'Official Monster Resort Lodgings:\n1. The Mummy Resort & Tomb-Service (Sarcophagus Suites)\n2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites)\n3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites)\n4. Vampire Manor: Eternal Night Inn (Coffin Suites)\n5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites)\n6. Ghostly B&B: Spectral Stay (Floating Spectral Suites)\n\nAmenities:\n- Blood Bar (Vampire Manor)\n- Afterlife Bistro (Mummy Resort)\n- Primal Buffet (Werewolf Lodge)\n- Lightning Spa (Castle Frankenstein)\n', 'meta': {'source': 'folder:/Users/akin.olusanya/Desktop/monster-resort-concierge/data/knowledge'}, 'score': 1.483931541336324}, {'text': 'Official Monster Resort Lodgings:\n1. The Mummy Resort & Tomb-Service (Sarcophagus Suites)\n2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites)\n3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites)\n4. Vampire Manor: Eternal Night Inn (Coffin Suites)\n5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites)\n6. Ghostly B&B: Spectral Stay (Floating Spectral Suites)\n\nAmenities:\n- Blood Bar (Vampire Manor)\n- Afterlife Bistro (Mummy Resort)\n- Primal Buffet (Werewolf Lodge)\n- Lightning Spa (Castle Frankenstein)\n', 'meta': {'source': 'folder:/Users/akin.olusanya/Desktop/monster-resort-concierge/data/knowledge'}, 'score': 1.483931541336324}, {'text': 'Official Monster Resort Lodgings:\n1. The Mummy Resort & Tomb-Service (Sarcophagus Suites)\n2. The Werewolf Lodge: Moon & Moor (Soundproofed Fur-Care Suites)\n3. Castle Frankenstein: High Voltage Luxury (Galvanic Suites)\n4. Vampire Manor: Eternal Night Inn (Coffin Suites)\n5. Zombie Bed & Breakfast: Bites & Beds (Shamble Suites)\n6. Ghostly B&B: Spectral Stay (Floating Spectral Suites)\n\nAmenities:\n- Blood Bar (Vampire Manor)\n- Afterlife Bistro (Mummy Resort)\n- Primal Buffet (Werewolf Lodge)\n- Lightning Spa (Castle Frankenstein)\n', 'meta': {'source': 'folder:/Users/akin.olusanya/Desktop/monster-resort-concierge/data/knowledge'}, 'score': 1.483931541336324}]}
# akin.olusanya@U-SH-HO-MAC211-5 monster-resort-concierge %Great — the output you just shared is super helpful and confirms everything is now working as expected on the RAG side!
# What the Output Tells Us

# rag.search('spa services') succeeded — it returned a dictionary with:
# 'ok': True
# 'query': 'spa services'
# 'results': a list of 5 matching documents

# All 5 results point to the same chunk of text (the full amenities list from amenities.txt), which includes:text...
# - Lightning Spa (Castle Frankenstein)
# ...
# The score is 1.48393 for every result (this is likely a raw distance/similarity score — higher is better in some vector DBs, but the repetition suggests your collection has duplicate or near-identical chunks).

# Why the Agent Was Still Falling Back
# Even though RAG returns data, your agent logic is not using the search results properly. From your earlier logs:

# Tool search_amenities is called successfully
# It returns a dict like {'ok': True, 'query': ..., 'results': [...]} (exactly what we see here)
# But the final response is pure LLM hallucination ("Alas, I must inform you that the Full Moon Café does not exist...") instead of referencing "Lightning Spa".

# This means the agent prompt or post-tool logic is:

# Not appending the results to the LLM prompt, or
# The LLM is instructed to ignore tool results, or
# There's a bug in how tool output is fed back into the conversation.

# Immediate Fix: Make the Agent Use RAG Results
# You need to modify the agent reply logic (likely in main.py or wherever _agent_reply or the chat endpoint lives) to include the RAG results in the LLM prompt.
# Example Patch (Add this in your agent function)
# Look for the part where it handles tool calls/results. Change it to something like this:
# Python# Inside _agent_reply or chat handler, after tool execution
# if tool_result and tool_result.get("ok") and tool_result.get("results"):
#     # Extract relevant text from RAG results
#     rag_context = "\n\n".join(
#         [r["text"] for r in tool_result["results"] if "text" in r]
#     )
#     # Add to messages/prompt
#     messages.append({
#         "role": "system",
#         "content": f"Use this retrieved information to answer accurately:\n{rag_context}\nDo NOT make up details not in this text."
#     })
#     # Then call LLM again with updated messages
#     final_response = client.chat.completions.create(..., messages=messages)
# else:
#     # Fallback only if no useful results
#     final_response = "I couldn't find specific information on that."
# Or simpler (if you're using a single prompt):
# Pythonprompt = f"""
# You are the Monster Resort concierge. Use ONLY the following information to answer:

# {rag_context if rag_context else "No specific knowledge available."}

# User question: {user_text}
# """
# Test It Immediately

# Add debug print to see raw tool output:In your agent code, after tool call:Pythonprint("RAW RAG RESULT:", json.dumps(tool_result, indent=2))
# Restart server:Bashuv run uvicorn app.main:app --reload
# Ask in chat: "What spa services do you have?"
# Check server logs — you should see RAW RAG RESULT: with the dict containing "Lightning Spa..."
# Agent response should now mention Lightning Spa at Castle Frankenstein instead of fallback.


# If You Want to Clean Up Duplicates
# Your collection has 38 documents, but searches return the same chunk 5 times → likely duplicate ingestion.
# Quick dedupe script (run once):
# Bashuv run python -c "
# from app.rag import VectorRAG
# from app.config import get_settings
# settings = get_settings()
# rag = VectorRAG(settings.rag_persist_dir, settings.rag_collection)
# rag.collection.delete(where={})  # WARNING: deletes ALL documents!
# texts = [...]  # paste your two texts here
# rag.ingest_texts(texts, source='clean')
# print('Reset and ingested. New count:', rag.collection.count())
# "
# Then re-test chat.
# Summary

# RAG is working — 38 docs, searches return real text (Lightning Spa is there!)
# Agent is not using the results → fix by appending rag_context to prompt.
# Add the debug print → test "spa services" → share logs/response.

# Let me know the new agent response or logs after adding the print — we'll make it use "Lightning Spa" correctly. You're right at the finish line! 🚀