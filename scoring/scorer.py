# scorer.py
# Purpose: Calculate a viral score (0-100) for any ad copy.
# Approach: Deterministic weighted formula + LLM-based metric extraction.
# Why not pure LLM? LLM alone gives random numbers — no engineering control.
# Our approach: LLM extracts variables, formula computes final score.

import os
import json
from groq import Groq
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
# load_dotenv() — .env file padhta hai aur
# GROQ_API_KEY environment variable set karta hai
# iske baad os.environ["GROQ_API_KEY"] accessible ho jaata hai

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
# Groq client banao — yeh LLM API se baat karta hai
# api_key — .env se automatically load hoti hai


# --- Pydantic Model --- 
class AdMetrics(BaseModel):
    hook_strength: int
    # Hook kitna strong hai — 1 to 10
    # Strong hook = reader ruk jaaye aur padhe

    sentiment_stability: int
    # Emotional tone consistent hai ya beech mein shift hoti hai — 1 to 10
    # Inconsistent tone = reader confused ho jaata hai

    keyword_density: int
    # Relevant keywords naturally included hain ya nahi — 1 to 10
    # Too few = SEO weak, too many = spammy lagta hai

    clarity: int
    # Message crystal clear hai ya confusing — 1 to 10
    # Reader ko 1 read mein samajh aana chahiye

# BaseModel — Pydantic class
# Purpose: LLM ka JSON output validate karna
# Agar LLM "hook_strength": "eight" return kare (string instead of int)
# Pydantic automatically error throw karega — silent bugs nahi honge


def extract_metrics_from_llm(ad_copy: str) -> AdMetrics:
    """
    Send ad copy to LLM and extract structured metrics as JSON.
    LLM sirf variables extract karta hai — score calculate nahi karta.
    """

    prompt = f"""You are an expert marketing analyst. Analyze the following ad copy and return a JSON object with exactly these 4 keys:

- hook_strength (integer 1-10): How compelling is the opening line? Does it make you stop scrolling?
- sentiment_stability (integer 1-10): Is the emotional tone consistent throughout? Or does it shift randomly?
- keyword_density (integer 1-10): Are relevant keywords naturally included without feeling forced or spammy?
- clarity (integer 1-10): Is the core message immediately clear after one read?

Ad Copy:
\"{ad_copy}\"

Return ONLY a valid JSON object. No explanation. No markdown. No extra text.
Example output: {{"hook_strength": 8, "sentiment_stability": 7, "keyword_density": 6, "clarity": 9}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        # Groq ka fastest free model
        # llama-3.3-70b — Meta ka 70 billion parameter model

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        # temperature — LLM ki "creativity" control karta hai
        # 0.0 = deterministic, always same output
        # 1.0 = very creative, random
        # 0.1 — almost deterministic — scoring ke liye best
        # hum chahte hain consistent results, creativity nahi

        max_tokens=150
        # sirf JSON chahiye — 150 tokens kaafi hain
        # zyada tokens = zyada cost aur time
    )

    raw_output = response.choices[0].message.content.strip()
    # .choices[0] — pehla (aur akela) response
    # .message.content — actual text
    # .strip() — extra whitespace/newlines remove karo

    # Clean the output — sometimes LLM adds markdown backticks
    if raw_output.startswith("```"):
        # agar LLM ne ```json ... ``` wrap kiya toh hata do
        raw_output = raw_output.split("```")[1]
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]
        # "json\n{...}" se "json" hata do

    parsed = json.loads(raw_output)
    # json.loads() — JSON string ko Python dictionary mein convert karo
    # json.load()  — file se padhta hai
    # json.loads() — string se padhta hai (s = string)

    return AdMetrics(**parsed)
    # **parsed — dictionary ko keyword arguments mein unpack karo
    # AdMetrics(hook_strength=8, sentiment_stability=7, ...)
    # Pydantic validate karega — wrong types pe error


def calculate_length_score(ad_copy: str) -> int:
    """
    Calculate length penalty score based on word count.
    Sweet spot: 15 to 50 words — not too short, not too long.
    """
    word_count = len(ad_copy.split())
    # .split() — words ki list banao
    # len() — count karo

    if 15 <= word_count <= 50:
        # Sweet spot — perfect length
        return 10

    elif word_count < 15:
        # Too short — reader ko enough info nahi milti
        score = max(1, word_count - 5)
        # max(1, ...) — minimum 1 return karo, kabhi 0 nahi
        # word_count=10 → score=5
        # word_count=6  → score=1
        return score

    else:
        # Too long — reader attention kho deta hai
        penalty = (word_count - 50) // 5
        # har 5 extra words pe 1 point penalty
        # word_count=55 → penalty=1 → score=9
        # word_count=80 → penalty=6 → score=4
        score = max(1, 10 - penalty)
        return score


def calculate_viral_score(ad_copy: str) -> dict:
    """
    Main function — calculate complete viral score for an ad.

    Steps:
    1. Calculate length score (deterministic)
    2. Extract LLM metrics (AI-powered)
    3. Apply weighted formula (deterministic)
    4. Return full breakdown

    Returns:
        dict with total_score and full breakdown
    """

    # --- Step 1: Length score ---
    word_count   = len(ad_copy.split())
    length_score = calculate_length_score(ad_copy)

    # --- Step 2: LLM metric extraction ---
    metrics = extract_metrics_from_llm(ad_copy)
    # metrics.hook_strength       — integer 1-10
    # metrics.sentiment_stability — integer 1-10
    # metrics.keyword_density     — integer 1-10
    # metrics.clarity             — integer 1-10

    # --- Step 3: Weighted formula ---
    # Weights decide karte hain kaunsa metric zyada important hai
    # Total weights = 1.0 (100%)
    W_length    = 0.15
    # 15% — length important hai but not the most critical factor

    W_hook      = 0.30
    # 30% — hook MOST important — agar pehli line weak hai,
    # reader scroll kar deta hai — baki kuch matter nahi karta

    W_sentiment = 0.20
    # 20% — consistent tone trust build karta hai

    W_keywords  = 0.20
    # 20% — keywords discoverability aur relevance ke liye

    W_clarity   = 0.15
    # 15% — message clear hona chahiye

    # Formula — har metric ko 0-100 scale pe convert karo phir weight apply karo
    raw_score = (
        W_length    * (length_score               * 10) +
        W_hook      * (metrics.hook_strength      * 10) +
        W_sentiment * (metrics.sentiment_stability * 10) +
        W_keywords  * (metrics.keyword_density    * 10) +
        W_clarity   * (metrics.clarity            * 10)
    )
    # metric * 10 — 1-10 scale ko 10-100 scale pe convert karo
    # phir weight multiply karo
    # sab add karo — final score 0-100

    final_score = round(raw_score)
    # round() — nearest integer pe round karo

    # --- Step 4: Return full breakdown ---
    return {
        "total_score": final_score,
        # 0-100 — overall viral potential

        "grade": _get_grade(final_score),
        # A/B/C/D/F — human readable grade

        "word_count": word_count,

        "breakdown": {
            "length_score":        length_score,
            "hook_strength":       metrics.hook_strength,
            "sentiment_stability": metrics.sentiment_stability,
            "keyword_density":     metrics.keyword_density,
            "clarity":             metrics.clarity
        },
        # breakdown — UI mein progress bars ke liye

        "weights": {
            "length":    W_length,
            "hook":      W_hook,
            "sentiment": W_sentiment,
            "keywords":  W_keywords,
            "clarity":   W_clarity
        }
        # weights — transparency ke liye — user dekh sake
        # ki score kaise calculate hua
    }


def _get_grade(score: int) -> str:
    """
    Convert numeric score to letter grade.
    Underscore prefix — private helper function.
    """
    if score >= 85:
        return "A — Excellent"
    elif score >= 70:
        return "B — Good"
    elif score >= 55:
        return "C — Average"
    elif score >= 40:
        return "D — Needs Work"
    else:
        return "F — Poor"