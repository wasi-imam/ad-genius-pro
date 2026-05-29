# analyst.py
# Purpose: Agent 1 — Compare user's ad against competitor ads
# and identify specific gaps as structured JSON.
# Input : user's ad copy + product description
# Output: list of gaps with severity levels

import os
import json
from groq import Groq
from dotenv import load_dotenv
from rag.retriever import get_similar_ads, format_for_agent

load_dotenv()
# Load GROQ_API_KEY from .env file

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def analyze_gaps(user_ad: str, product_description: str) -> list:
    """
    Compare user's ad against top competitor ads from ChromaDB.
    Returns a list of gap dictionaries.

    Parameters:
        user_ad             : str — the ad copy user wants to improve
        product_description : str — what the product is (for RAG search)

    Returns:
        list of dicts — each dict has: gap, severity, competitor_does
    """

    # --- Step 1: Retrieve similar competitor ads from ChromaDB ---
    similar_ads = get_similar_ads(product_description, n_results=5)
    # Use product_description for RAG search — not the ad itself
    # Because we want competitors in the SAME product category
    # Example: "running shoes" → Nike, Adidas, Reebok ads

    competitor_context = format_for_agent(similar_ads)
    # Convert list of ads to readable text block
    # This goes into the LLM prompt as context

    # --- Step 2: Build the analyst prompt ---
    prompt = f"""You are a senior marketing analyst with 15 years of experience analyzing digital ad campaigns.

Your task: Compare the USER'S AD against the TOP COMPETITOR ADS and identify specific, actionable gaps.

USER'S AD:
\"\"\"{user_ad}\"\"\"

{competitor_context}

Analyze the user's ad and identify gaps by comparing it to what competitors are doing better.

Return ONLY a JSON array. Each object must have exactly these 3 keys:
- "gap": specific problem found (be concrete, not vague)
- "severity": exactly one of "high", "medium", or "low"
- "competitor_does": what competitors do instead (reference specific competitors)

Severity guide:
- high   : directly hurts conversions — missing CTA, no value proposition, wrong tone
- medium : weakens the ad but not critical — missing price, weak hook, no social proof
- low    : minor polish — keyword opportunity, platform optimization

Return between 3 and 6 gaps. No explanation. No markdown. Only the JSON array.

Example format:
[
  {{
    "gap": "No clear call-to-action",
    "severity": "high",
    "competitor_does": "Nike and Adidas both end with 'Shop Now' or 'Order Today'"
  }}
]"""

    # --- Step 3: Call LLM ---
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a marketing analyst. Always respond with valid JSON arrays only. No markdown, no explanation."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        # Low temperature — we want consistent, analytical output
        # Not creative — analytical

        max_tokens=800
        # Enough for 3-6 gap objects
    )

    raw_output = response.choices[0].message.content.strip()

    # --- Step 4: Clean and parse JSON ---
    if "```" in raw_output:
        # Remove markdown code blocks if LLM added them
        raw_output = raw_output.split("```")[1]
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]

    gaps = json.loads(raw_output)
    # Parse JSON string into Python list

    # --- Step 5: Validate structure ---
    validated_gaps = []
    for gap in gaps:
        if all(key in gap for key in ["gap", "severity", "competitor_does"]):
            # all() — check karo ki teeno keys exist karti hain
            # agar koi key missing ho — us gap ko skip karo
            # silent crash prevention

            # Normalize severity — LLM kabhi kabhi wrong case deta hai
            gap["severity"] = gap["severity"].lower().strip()
            if gap["severity"] not in ["high", "medium", "low"]:
                gap["severity"] = "medium"
                # Unknown severity ko medium set karo

            validated_gaps.append(gap)

    return validated_gaps