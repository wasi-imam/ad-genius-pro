# strategy_builder.py
# Purpose: Generate 3 parallel ad rewrites using different strategies
# Strategies: Conversion, Emotional, Urgency
#
# KEY DESIGN:
# 1. On-demand only — user clicks button to generate
# 2. Analyst gaps SHARED — run once, used by all 3
# 3. 3 builders run IN PARALLEL — ThreadPoolExecutor
# 4. Scorer evaluates all 3 — winner = highest score

import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from groq import Groq
from dotenv import load_dotenv

try:
    import streamlit as st
    if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

from config import (
    LLM_MODEL,
    LLM_TEMPERATURE_BUILDER,
    MAX_RETRIES,
    RETRY_DELAY,
    MAX_TOKENS_BUILDER
)
from utils.cache import get_cached, set_cache
from utils.logger import builder_logger

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

STRATEGIES = {
    "Conversion": {
        "name":        "Conversion Focused",
        "icon":        "🎯",
        "description": "Maximum clicks and purchases",
        "use_case":    "Performance campaigns, direct sales, D2C brands",
        "instruction": (
            "Focus on: price, specific offer, and strong CTA. "
            "Tone: direct, persuasive, action-oriented. "
            "Must include: a clear action verb (Buy/Order/Get/Shop). "
            "Lead with the strongest benefit or price point."
        )
    },
    "Emotional": {
        "name":        "Emotional",
        "icon":        "❤️",
        "description": "Connect with desire or pain point",
        "use_case":    "Brand awareness, social media, lifestyle products",
        "instruction": (
            "Focus on: emotional pain point or aspiration. "
            "Tone: empathetic, warm, inspiring. "
            "Must include: a feeling or transformation the user will experience. "
            "Sell the emotion and identity, not just features."
        )
    },
    "Urgency": {
        "name":        "Urgency Driven",
        "icon":        "⏰",
        "description": "Force immediate action via FOMO",
        "use_case":    "Flash sales, festivals, high-competition categories",
        "instruction": (
            "Focus on: urgency and scarcity. "
            "Tone: urgent, FOMO-inducing, high energy. "
            "Must include: time pressure OR stock scarcity. "
            "Use phrases like: limited time, ending soon, only X left, hurry."
        )
    }
}


def rewrite_with_strategy(original_ad, gaps, strategy_key):
    strategy  = STRATEGIES[strategy_key]
    gaps_str  = json.dumps(gaps, sort_keys=True)
    cache_key = "strategy:{}:{}:{}".format(
        strategy_key, original_ad[:50], gaps_str[:50]
    )
    cached = get_cached(cache_key)
    if cached:
        builder_logger.info("Cache hit — strategy {}".format(strategy_key))
        return cached

    gap_instructions = ""
    for i, gap in enumerate(gaps, 1):
        if isinstance(gap, dict):
            severity  = gap.get("severity", "medium").upper()
            gap_text  = gap.get("gap", "Improve the ad")
            reference = gap.get("competitor_does", "Follow best practices")
            gap_instructions += "{}. [{}] {}\n   Reference: {}\n\n".format(
                i, severity, gap_text, reference
            )
        else:
            gap_instructions += "{}. {}\n".format(i, gap)

    prompt = """You are a world-class copywriter specializing in {sname} advertising.

Rewrite the following ad using the {sname} strategy.

ORIGINAL AD:
\"{ad}\"

GAPS TO FIX:
{gaps}

STRATEGY INSTRUCTIONS:
{instruction}

RULES:
1. Fix ALL gaps listed above
2. Keep the same product
3. Keep between 20 and 55 words
4. Apply the {sname} strategy strictly
5. First line must be a stronger hook

After the rewritten ad, add "---" then list changes starting with "CHANGES:".

Format:
[Rewritten ad here]
---
CHANGES:
- Change 1
- Change 2""".format(
        sname=strategy["name"],
        ad=original_ad,
        gaps=gap_instructions,
        instruction=strategy["instruction"]
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert copywriter. Follow format and strategy instructions exactly."},
                    {"role": "user",   "content": prompt}
                ],
                temperature=LLM_TEMPERATURE_BUILDER,
                max_tokens=MAX_TOKENS_BUILDER
            )
            raw = response.choices[0].message.content.strip()
            if "---" in raw:
                parts        = raw.split("---", 1)
                rewritten_ad = parts[0].strip()
                changes_raw  = parts[1].strip()
                changes_text = changes_raw.replace("CHANGES:", "").strip()
            else:
                rewritten_ad = raw
                changes_text = "Ad rewritten using {} strategy.".format(strategy["name"])

            if not rewritten_ad.strip():
                raise ValueError("Empty rewrite")

            result = {
                "strategy_key":  strategy_key,
                "strategy_name": strategy["name"],
                "strategy_icon": strategy["icon"],
                "use_case":      strategy["use_case"],
                "description":   strategy["description"],
                "rewritten_ad":  rewritten_ad,
                "changes_made":  changes_text,
                "word_count":    len(rewritten_ad.split()),
                "score":         None,
                "grade":         None,
                "dimensions":    None,
                "is_winner":     False
            }
            set_cache(cache_key, result)
            builder_logger.info("Strategy {} complete".format(strategy_key))
            return result

        except Exception as e:
            last_error = str(e)
            builder_logger.warning("Strategy {} attempt {} failed: {}".format(
                strategy_key, attempt+1, e
            ))
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    builder_logger.error("Strategy {} all retries failed.".format(strategy_key))
    return {
        "strategy_key":  strategy_key,
        "strategy_name": strategy["name"],
        "strategy_icon": strategy["icon"],
        "use_case":      strategy["use_case"],
        "description":   strategy["description"],
        "rewritten_ad":  original_ad,
        "changes_made":  "Strategy generation failed.",
        "word_count":    len(original_ad.split()),
        "score":         None,
        "grade":         None,
        "dimensions":    None,
        "is_winner":     False
    }


def generate_all_strategies(original_ad, gaps):
    from scoring.explainable_scorer import calculate_explainable_score

    builder_logger.info("Generating 3 strategies in parallel...")
    strategy_keys = list(STRATEGIES.keys())
    results = {}

    # Step 1 — 3 rewrites in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(rewrite_with_strategy, original_ad, gaps, key): key
            for key in strategy_keys
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                builder_logger.error("Strategy {} failed: {}".format(key, e))

    # Step 2 — Score all 3 in parallel
    def score_strategy(key):
        result = results[key]
        scored = calculate_explainable_score(result["rewritten_ad"])
        if not scored.get("error"):
            result["score"]      = scored["total_score"]
            result["grade"]      = scored["grade"]
            result["dimensions"] = scored["dimensions"]
        else:
            result["score"]      = 0
            result["grade"]      = "N/A"
            result["dimensions"] = []
        return key, result

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(score_strategy, key): key for key in results}
        for future in as_completed(futures):
            key, result = future.result()
            results[key] = result

    # Step 3 — Winner
    valid = {k: v for k, v in results.items() if v.get("score") and v["score"] > 0}
    winner_key = max(valid, key=lambda k: valid[k]["score"]) if valid else None
    if winner_key:
        results[winner_key]["is_winner"] = True

    # Step 4 — Dimension comparison
    dim_names = [
        "Hook Strength", "Value Proposition", "Call to Action",
        "Emotional Trigger", "Clarity & Readability", "Length Optimization"
    ]
    dim_comparison = {}
    for dim in dim_names:
        dim_comparison[dim] = {}
        for key in strategy_keys:
            if results.get(key, {}).get("dimensions"):
                score = next(
                    (d["score"] for d in results[key]["dimensions"] if d["dimension"] == dim),
                    0
                )
                dim_comparison[dim][key] = score

    recommendation = (
        "Choose based on your campaign goal: "
        "Conversion for direct sales, "
        "Emotional for brand awareness, "
        "Urgency for flash sales and festivals."
    )

    return {
        "strategies":           [results[k] for k in strategy_keys if k in results],
        "winner_key":           winner_key,
        "winner_score":         results[winner_key]["score"] if winner_key else 0,
        "dimension_comparison": dim_comparison,
        "recommendation":       recommendation
    }
