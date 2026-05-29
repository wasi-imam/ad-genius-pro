# builder.py
# Purpose: Agent 2 — Take the gaps identified by analyst
# and rewrite the ad copy to fix all of them.
# Input : original ad + list of gaps from analyst
# Output: improved ad copy + explanation of changes

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def rewrite_ad(original_ad: str, gaps: list) -> dict:
    """
    Rewrite the ad copy to fix all identified gaps.

    Parameters:
        original_ad : str  — the original ad copy
        gaps        : list — gaps from analyst agent

    Returns:
        dict with: rewritten_ad, changes_made, word_count
    """

    # --- Step 1: Format gaps into clear instructions ---
    if not gaps:
        return {
            "rewritten_ad": original_ad,
            "changes_made": "No gaps found — original ad returned unchanged.",
            "word_count": len(original_ad.split())
        }

    gap_instructions = ""
    for i, gap in enumerate(gaps, 1):
        gap_instructions += f"{i}. [{gap['severity'].upper()}] Fix: {gap['gap']}\n"
        gap_instructions += f"   Reference: {gap['competitor_does']}\n\n"
    # Format each gap as a numbered instruction
    # Builder agent gets very specific instructions — not vague

    # --- Step 2: Build the builder prompt ---
    prompt = f"""You are a world-class copywriter who specializes in high-converting digital ads.

Your task: Rewrite the following ad copy to fix all identified gaps while preserving the product's core identity and brand tone.

ORIGINAL AD:
\"\"\"{original_ad}\"\"\"

GAPS TO FIX (in order of priority):
{gap_instructions}

RULES for rewriting:
1. Fix ALL gaps listed above — this is mandatory
2. Keep the same product — do not change what is being sold
3. Maintain the brand's tone and voice
4. Keep the rewritten ad between 20 and 55 words
5. The new hook (first line) must be stronger than the original
6. End with a clear call-to-action if missing

After the rewritten ad, add a separator line "---" and then list the key changes you made in 3-5 bullet points starting with "CHANGES:".

Format your response exactly like this:
[Your rewritten ad copy here]
---
CHANGES:
- Change 1
- Change 2
- Change 3"""

    # --- Step 3: Call LLM ---
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are an expert copywriter. Follow the format instructions exactly."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        # Higher temperature than analyst — we WANT creativity here
        # Analyst = analytical (0.2), Builder = creative (0.7)

        max_tokens=500
    )

    raw_output = response.choices[0].message.content.strip()

    # --- Step 4: Parse the response ---
    if "---" in raw_output:
        parts = raw_output.split("---", 1)
        # split("---", 1) — sirf pehli occurrence pe split karo
        # maxsplit=1 — do parts: [ad_copy, changes]

        rewritten_ad = parts[0].strip()
        changes_section = parts[1].strip()

        # Clean up changes section
        if "CHANGES:" in changes_section:
            changes_text = changes_section.replace("CHANGES:", "").strip()
        else:
            changes_text = changes_section

    else:
        # Agar separator nahi mila — poora output ad copy maano
        rewritten_ad = raw_output
        changes_text = "Changes made based on identified gaps."

    return {
        "rewritten_ad": rewritten_ad,
        # Improved ad copy

        "changes_made": changes_text,
        # Bullet points of what was changed

        "word_count": len(rewritten_ad.split())
        # Word count of new ad
    }


def run_full_pipeline(user_ad: str, product_description: str) -> dict:
    """
    Run the complete 2-agent pipeline:
    Analyst → Builder

    This is the main function called by app.py.

    Parameters:
        user_ad             : str — user's original ad
        product_description : str — product being advertised

    Returns:
        dict with: gaps, rewritten_ad, changes_made, word_count
    """
    from agents.analyst import analyze_gaps
    # Import here — not at top — to avoid circular imports
    # analyst imports from rag, builder imports from analyst
    # importing at function level breaks the circular dependency

    # --- Agent 1: Analyze ---
    print("Agent 1 (Analyst) running...")
    gaps = analyze_gaps(user_ad, product_description)
    print(f"Gaps identified: {len(gaps)}")

    # --- Agent 2: Build ---
    print("Agent 2 (Builder) running...")
    result = rewrite_ad(original_ad=user_ad, gaps=gaps)
    print("Rewrite complete.")

    # --- Combine results ---
    return {
        "gaps":         gaps,
        # List of gap dicts from analyst

        "rewritten_ad": result["rewritten_ad"],
        # Improved ad from builder

        "changes_made": result["changes_made"],
        # What was changed and why

        "word_count":   result["word_count"]
        # New ad word count
    }