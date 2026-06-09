# app.py
# Purpose: Main Streamlit application — complete UI.
#
# WHAT CHANGED FROM ORIGINAL:
# 1. Better CSS — professional design
# 2. Analysis history — last 5 analyses saved
# 3. Word diff — exactly kya badla highlight karna
# 4. Better loading messages — step by step progress
# 5. Metrics display improved — visual score card
# 6. Error handling integrated — user friendly messages

import streamlit as st
import time
import concurrent.futures

from scoring.scorer    import calculate_viral_score
from agents.builder    import run_full_pipeline
from rag.retriever     import get_similar_ads
from utils.pdf_exporter import generate_report
from utils.logger      import app_logger

# ============================================================
# CHROMADB AUTO-BUILD
# WHAT: Agar chroma_db/ folder nahi hai toh embedder run karo
# WHY:  chroma_db/ gitignore mein hai — deploy pe nahi hogi
#       Pehli baar automatically build ho jaaye
# WHERE: App start hone pe, kuch bhi render hone se pehle
# ============================================================
import os
if not os.path.exists("./chroma_db"):
    app_logger.info("ChromaDB not found — building now...")
    import subprocess
    subprocess.run(["python", "rag/embedder.py"], check=True)
    app_logger.info("ChromaDB built successfully.")


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title = "AdCopilot",
    page_icon  = "🎯",
    layout     = "wide",
)

# ============================================================
# CUSTOM CSS — UPGRADED
# WHAT CHANGED: Much more detailed styling
# WHY: Default Streamlit looks amateur — recruiters notice
# ============================================================
st.markdown("""
<style>
    /* Main header */
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        color: #534AB7;
        text-align: center;
        margin-bottom: 0.2rem;
        letter-spacing: -1px;
    }

    /* Subtitle */
    .sub-header {
        font-size: 1rem;
        color: #888;
        text-align: center;
        margin-bottom: 2rem;
    }

    /* Big score display */
    .score-container {
        background: linear-gradient(135deg, #534AB7 0%, #7B74D4 100%);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        color: white;
        margin-bottom: 1rem;
    }
    .score-number {
        font-size: 4.5rem;
        font-weight: 800;
        line-height: 1;
        color: white;
    }
    .score-grade {
        font-size: 1.1rem;
        color: rgba(255,255,255,0.85);
        margin-top: 0.5rem;
    }

    /* Metric cards */
    .metric-card {
        background: var(--background-color);
        border: 1px solid #E0DFF5;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
        margin-bottom: 0.3rem;
    }
    .metric-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #534AB7;
    }

    /* Gap cards */
    .gap-high {
        background: #FEF2F2;
        border-left: 4px solid #EF4444;
        border-radius: 0 8px 8px 0;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
    }
    .gap-medium {
        background: #FFFBEB;
        border-left: 4px solid #F59E0B;
        border-radius: 0 8px 8px 0;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
    }
    .gap-low {
        background: #F0FDF4;
        border-left: 4px solid #22C55E;
        border-radius: 0 8px 8px 0;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
    }
    .gap-title {
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.25rem;
    }
    .gap-sub {
        font-size: 0.82rem;
        color: #666;
    }

    /* Ad copy boxes */
    .ad-box-original {
        background: #FEF2F2;
        border: 1px solid #FECACA;
        border-radius: 12px;
        padding: 1.25rem;
        font-size: 1rem;
        line-height: 1.6;
        min-height: 100px;
    }
    .ad-box-new {
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-radius: 12px;
        padding: 1.25rem;
        font-size: 1rem;
        line-height: 1.6;
        min-height: 100px;
    }

    /* Word diff */
    .word-added   { background: #BBF7D0; border-radius: 3px; padding: 0 3px; }
    .word-removed {
        background: #FECACA;
        border-radius: 3px;
        padding: 0 3px;
        text-decoration: line-through;
        color: #991B1B;
    }

    /* History card */
    .history-card {
        background: var(--background-color);
        border: 1px solid #E0DFF5;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
    }

    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #534AB7;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #E0DFF5;
    }

    /* Progress bar color */
    .stProgress > div > div {
        background: linear-gradient(90deg, #534AB7, #7B74D4);
    }

    /* Button styling */
    .stButton > button[kind="primary"] {
        background: #534AB7;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.6rem 2rem;
    }
    .stButton > button[kind="primary"]:hover {
        background: #4339A0;
        border: none;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================
st.markdown('<p class="main-header">🎯 AdCopilot</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">'
    'AI-powered ad optimization — RAG pipeline · Deterministic scoring · 2-agent critique'
    '</p>',
    unsafe_allow_html=True
)
st.divider()


# ============================================================
# SESSION STATE — UPGRADED
# WHAT CHANGED: history list added
# WHY: User apne purane analyses compare kar sake
# ============================================================
defaults = {
    "analysis_done":  False,
    "strategies":     None,
    "score_data":     None,
    "gaps":           None,
    "rewritten_ad":   None,
    "changes_made":   None,
    "original_ad":    None,
    "product_desc":   None,
    "similar_ads":    None,
    "history":        [],
    # NEW: list of past analyses
    # Each item: {product, original_ad, score, grade, timestamp}
}

for key, default_val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default_val
# Loop se sab defaults set karo — cleaner than writing each one


# ============================================================
# HELPER: Word diff function
# NEW: Pehle nahi tha
# WHAT: Do texts compare karke differences highlight karo
# WHERE: Tab 2 mein original vs rewritten show karte waqt
# WHY: User clearly dekhe kya change hua — without guessing
# ============================================================
def generate_word_diff(original: str, rewritten: str) -> str:
    """
    Generate HTML showing word-level differences.
    Green = added words, Red strikethrough = removed words.

    CHANGED: Set operations → difflib.SequenceMatcher
    WHY: Set operations order aur repetition ignore karte the.
         "best best product" → "best product" ko set
         same maanta tha — koi change nahi dikhata.
         difflib order-aware aur repetition-aware hai.
    """
    import difflib

    original_words  = original.split()
    rewritten_words = rewritten.split()

    # SequenceMatcher — do sequences compare karta hai
    # autojunk=False — chhote texts mein junk detection off karo
    matcher = difflib.SequenceMatcher(
        None, original_words, rewritten_words, autojunk=False
    )

    html_parts = []

    # get_opcodes() — list of (tag, i1, i2, j1, j2) tuples
    # tag = "equal", "insert", "delete", "replace"
    # i1:i2 = original mein range
    # j1:j2 = rewritten mein range
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            # Same words — no highlight
            html_parts.extend(rewritten_words[j1:j2])

        elif tag == "insert":
            # Words added in rewritten — green highlight
            for word in rewritten_words[j1:j2]:
                html_parts.append(
                    '<span class="word-added">{}</span>'.format(word)
                )

        elif tag == "delete":
            # Words removed from original — red strikethrough
            for word in original_words[i1:i2]:
                html_parts.append(
                    '<span class="word-removed">{}</span>'.format(word)
                )

        elif tag == "replace":
            # Words changed — old = red, new = green
            for word in original_words[i1:i2]:
                html_parts.append(
                    '<span class="word-removed">{}</span>'.format(word)
                )
            for word in rewritten_words[j1:j2]:
                html_parts.append(
                    '<span class="word-added">{}</span>'.format(word)
                )

    return " ".join(html_parts)

def save_to_history(product_desc, original_ad, score_data):
    """Save current analysis summary to session history."""
    import datetime

    entry = {
        "product":    product_desc[:40] + "..." if len(product_desc) > 40 else product_desc,
        "original":   original_ad[:60] + "..." if len(original_ad) > 60 else original_ad,
        "score":      score_data["total_score"],
        "grade":      score_data["grade"],
        "timestamp":  datetime.datetime.now().strftime("%H:%M:%S")
    }

    st.session_state.history.insert(0, entry)
    # insert(0, ...) — naya item shuruwat mein daalo
    # Latest analysis sabse pehle dikhe

    if len(st.session_state.history) > 5:
        st.session_state.history = st.session_state.history[:5]
        # Maximum 5 entries — purane hata do
        # [:5] — pehle 5 rakho


# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📝  Input & Insights",
    "⚡  Critique & Rewrite",
    "📊  History",
    # NEW tab — pehle 3 tabs the, ab 4
    "📥  Export"
])


# ============================================================
# TAB 1 — INPUT
# ============================================================
with tab1:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<p class="section-header">Your Ad Details</p>', unsafe_allow_html=True)

        product_desc = st.text_input(
            "Product Description",
            placeholder="e.g. premium running shoes for athletes",
            help="Used to find similar competitor ads via RAG"
        )

        ad_draft = st.text_area(
            "Your Ad Draft",
            placeholder="e.g. Great shoes. Buy now.",
            height=140,
            help="The ad copy you want to analyze and improve"
        )

        # NEW: Word count live display
        # WHAT: User type kare — word count update ho
        # WHY: 200 word limit hai — user ko pata hona chahiye
        if ad_draft:
            wc = len(ad_draft.split())
            if wc > 200:
                st.error(f"Too long: {wc} words (max 200)")
            elif wc > 150:
                st.warning(f"Getting long: {wc} words")
            else:
                st.caption(f"Word count: {wc}/200")

    with col_right:
        st.markdown('<p class="section-header">Upload Competitor PDF</p>', unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Optional — large files handled with streaming",
            type=["pdf"]
        )

        if uploaded_file:
            file_mb = uploaded_file.size / (1024 * 1024)
            st.caption(f"File: {uploaded_file.name} ({file_mb:.1f} MB)")

            if st.button("Process PDF", type="secondary"):
                from rag.pdf_ingestion import process_pdf_streaming

                progress_bar = st.progress(0)
                status_text  = st.empty()

                def update_progress(pct, msg):
                    progress_bar.progress(pct)
                    status_text.text(msg)

                with st.spinner("Streaming PDF into vector DB..."):
                    result = process_pdf_streaming(
                        uploaded_file,
                        update_progress
                    )

                progress_bar.progress(1.0)
                st.success(
                    f"Indexed {result['total_chunks']} chunks "
                    f"from {result['total_pages']} pages"
                )

    st.divider()

    # Analyze button
    if st.button("🔍 Analyze My Ad", type="primary", use_container_width=True):

        # Validation
        if not product_desc.strip():
            st.error("Please enter a product description.")
            st.stop()

        if not ad_draft.strip():
            st.error("Please enter your ad draft.")
            st.stop()

        if len(ad_draft.split()) > 200:
            st.error("Ad copy too long — maximum 200 words.")
            st.stop()

        app_logger.info(f"Analysis started for product: {product_desc[:50]}")

        # NEW: Step by step progress messages
        # WHAT CHANGED: Single spinner → multiple step indicators
        # WHY: User ko pata chale kya ho raha hai — better UX
        status = st.empty()

        status.info("🔍 Step 1/3 — Finding similar competitor ads...")
        with st.spinner(""):
            similar_ads = get_similar_ads(product_desc, n_results=5)
            st.session_state.similar_ads = similar_ads
            st.session_state.product_desc = product_desc
            st.session_state.original_ad  = ad_draft

        status.info("📊 Step 2/3 — Scoring + Analysis in parallel...")
        with st.spinner(""):
            # PARALLEL EXECUTION — ThreadPoolExecutor
            # WHAT: scorer aur analyst dono ek saath chalao
            # WHY:  Dono independent hain — sequential mein 6 sec, ab 3 sec
            # HOW:  submit() tasks queue karta hai, result() wait karta hai
            from agents.analyst import analyze_gaps
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_score = executor.submit(calculate_viral_score, ad_draft)
                future_gaps  = executor.submit(analyze_gaps, ad_draft, product_desc)
                score_data = future_score.result()
                gaps       = future_gaps.result()
            if score_data.get("error"):
                st.error(f"Scoring error: {score_data['error_msg']}")
                app_logger.error(f"Scoring failed: {score_data['error_msg']}")
                st.stop()
            st.session_state.score_data = score_data

        status.info("🤖 Step 3/3 — Rewriting your ad...")
        with st.spinner(""):
            # Builder gaps ka use karta hai — sequential rehna zaroori hai
            from agents.builder import rewrite_ad
            result = rewrite_ad(original_ad=ad_draft, gaps=gaps)
            pipeline = {
                "success":      True,
                "gaps":         gaps,
                "rewritten_ad": result["rewritten_ad"],
                "changes_made": result["changes_made"],
                "word_count":   result["word_count"]
            }
            if not pipeline.get("success", True):
                st.error("Analysis failed — please try again.")
                app_logger.error("Pipeline failed")
                st.stop()

            st.session_state.gaps          = pipeline["gaps"]
            st.session_state.rewritten_ad  = pipeline["rewritten_ad"]
            st.session_state.changes_made  = pipeline["changes_made"]
            st.session_state.analysis_done = True

        # NEW: Save to history
        save_to_history(product_desc, ad_draft, score_data)
        app_logger.info(f"Analysis complete. Score: {score_data['total_score']}")

        status.success("✅ Analysis complete — check the next tabs!")

    # Show competitor ads
    if st.session_state.similar_ads:
        st.markdown('<p class="section-header">Similar Competitor Ads Found</p>', unsafe_allow_html=True)

        for ad in st.session_state.similar_ads:
            with st.expander(
                f"🏢 {ad['brand']} — {ad['similarity_score']:.0%} match | {ad['platform']}"
            ):
                st.write(f"**Ad Copy:** {ad['ad_copy']}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Semantic",  f"{ad.get('semantic_score', 0):.0%}")
                c2.metric("Keyword",   f"{ad.get('keyword_score', 0):.0%}")
                c3.metric("Has CTA",   ad["has_cta"])
                c4.metric("Sentiment", ad["sentiment"])


# ============================================================
# TAB 2 — CRITIQUE & REWRITE — UPGRADED
# ============================================================
with tab2:
    if not st.session_state.analysis_done:
        st.info("👆 Run analysis in Tab 1 first.")
    else:
        # ─────────────────────────────────────────────
        # EXPLAINABLE SCORECARD
        # ─────────────────────────────────────────────
        from scoring.explainable_scorer import calculate_explainable_score

        # Run explainable scorer — cached after first run
        expl = calculate_explainable_score(st.session_state.original_ad)

        if expl.get("error"):
            st.error(expl.get("error_msg", "Scoring failed."))
        else:
            # ── TOP SUMMARY ──
            score    = expl["total_score"]
            grade    = expl["grade"]
            one_liner = expl["one_liner"]

            col_score, col_summary = st.columns([1, 2])
            with col_score:
                color = "#2ecc71" if score >= 70 else "#f39c12" if score >= 50 else "#e74c3c"
                st.markdown(f"""
                <div style="background:{color}22; border:2px solid {color};
                     border-radius:16px; padding:24px; text-align:center;">
                    <div style="font-size:3.5rem; font-weight:900;
                         color:{color};">{score}</div>
                    <div style="font-size:1.2rem; font-weight:700;
                         color:{color};">{grade}</div>
                    <div style="color:#888; font-size:0.8rem; margin-top:4px;">
                        out of 100</div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"Words: {expl['word_count']}")

            with col_summary:
                st.markdown("### Summary")
                st.info(one_liner)
                st.markdown("**Top priority fixes:**")
                for fix in expl["top_3_fixes"]:
                    st.markdown(
                        f"**#{fix['priority']} {fix['dimension']}** — "
                        f"{fix['action']} *({fix['impact']})*"
                    )

            st.divider()
            # ── BENCHMARK CARD ──
            from scoring.benchmark_engine import calculate_benchmark
            bench = calculate_benchmark(
                user_score     = expl["total_score"],
                user_dimensions= expl["dimensions"],
                product_desc   = st.session_state.product_desc
            )

            pos      = bench["market_position"]
            pct      = bench["percentile"]
            ind_avg  = bench["industry_avg"]
            cat_avg  = bench["category_avg"]
            cat      = bench["category"]
            top_score= bench["global_top_score"]
            top_brand= bench["global_top_brand"]
            gap_avg  = bench["gap_to_avg"]
            gap_top  = bench["gap_to_top"]
            insight  = bench["insight"]

            pos_color = "#2ecc71" if pct >= 60 else "#f39c12" if pct >= 30 else "#e74c3c"

            st.markdown("### Market Position")
            st.markdown(
                f'<div style="background:{pos_color}11; border:2px solid {pos_color}; '
                f'border-radius:12px; padding:16px; margin-bottom:16px;">'                f'<h4 style="color:{pos_color}; margin:0;">'
                f'{pos} — You beat {pct}% of competitor ads</h4>'                f'<p style="color:#888; margin:4px 0 0 0; font-size:0.9rem;">'                f'Category: {cat}</p></div>',
                unsafe_allow_html=True
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Your Score",      score,     delta=None)
            c2.metric("Industry Avg",    ind_avg,   delta=round(score - ind_avg, 1))
            c3.metric("Top Competitor",  f"{top_score} ({top_brand})", delta=None)

            ca, cb2 = st.columns(2)
            ca.metric("Category Avg",    cat_avg,   delta=round(score - cat_avg, 1))
            cb2.metric("Gap to Top",     gap_top,   delta=None)

            st.markdown("**💡 Insight:**")
            st.info(insight)

            st.markdown("### Dimension vs Industry")
            dh1, dh2, dh3, dh4 = st.columns([3,1,1,1])
            dh1.markdown("**Dimension**")
            dh2.markdown("**Yours**")
            dh3.markdown("**Industry**")
            dh4.markdown("**Gap**")

            for dg in bench["dimension_gaps"]:
                dc1, dc2, dc3, dc4 = st.columns([3,1,1,1])
                dc1.write(dg["dimension"])
                dc2.write(dg["user_score"])
                dc3.write(dg["industry_avg"])
                gap_val = dg["gap"]
                gap_str = "+{:.1f}".format(gap_val) if gap_val > 0 else "{:.1f}".format(gap_val)
                gap_col = "green" if gap_val > 0 else "red" if gap_val < -2 else "orange"
                dc4.markdown(
                    f'<span style="color:{gap_col}; font-weight:600;">{gap_str}</span>',
                    unsafe_allow_html=True
                )

            st.divider()

            # ── DIMENSION BREAKDOWN TABLE ──
            st.markdown("### Score Breakdown")

            # Header
            h1, h2, h3, h4 = st.columns([3, 1, 1, 2])
            h1.markdown("**Dimension**")
            h2.markdown("**Score**")
            h3.markdown("**Points**")
            h4.markdown("**Rating**")

            rating_color = {
                "Excellent": "🟢",
                "Good":      "🟢",
                "Average":   "🟡",
                "Poor":      "🔴",
                "Very Poor": "🔴"
            }

            for dim in expl["dimensions"]:
                c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                c1.write(dim["dimension"])
                c2.write(f"{dim['score']}/10")
                c3.write(f"{dim['weighted']}")
                icon = rating_color.get(dim["rating"], "⚪")
                c4.write(f"{icon} {dim['rating']}")

            # Total row
            t1, t2, t3, t4 = st.columns([3, 1, 1, 2])
            t1.markdown("**TOTAL**")
            t2.markdown("")
            t3.markdown(f"**{score}**")
            t4.markdown("")

            st.divider()

            # ── EXPANDABLE DIMENSION CARDS ──
            st.markdown("### Detailed Analysis")

            icons = {
                "Hook Strength":        "🎣",
                "Value Proposition":    "💎",
                "Call to Action":       "📢",
                "Emotional Trigger":    "❤️",
                "Clarity & Readability":"📖",
                "Length Optimization":  "📏",
            }

            for dim in expl["dimensions"]:
                icon  = icons.get(dim["dimension"], "📊")
                label = f"{icon} {dim['dimension']} — {dim['score']}/10 — {dim['rating']}"
                with st.expander(label):
                    ea, eb = st.columns(2)
                    with ea:
                        st.markdown("**📍 Evidence from your ad:**")
                        st.code(dim["evidence"], language=None)
                        st.markdown("**❓ Why this score:**")
                        st.write(dim["reason"])
                    with eb:
                        st.markdown("**✅ How to improve:**")
                        st.info(dim["suggestion"])
                        pts = dim["weighted"]
                        st.caption(f"This dimension contributes {pts} pts to total")

            st.divider()

            # ── ORIGINAL vs REWRITTEN ──
            st.markdown("### Original vs Optimized Ad")
            col_orig, col_new = st.columns(2)
            with col_orig:
                st.markdown("**🔴 Original Ad**")
                st.markdown(
                    f'<div class="ad-box-original">{st.session_state.original_ad}</div>',
                    unsafe_allow_html=True
                )
            with col_new:
                st.markdown("**🟢 Optimized Ad**")
                st.markdown(
                    f'<div class="ad-box-new">{st.session_state.rewritten_ad}</div>',
                    unsafe_allow_html=True
                )

            # ── BEFORE vs AFTER SCORE ──
            st.markdown("### Before vs After Score")
            from scoring.explainable_scorer import calculate_explainable_score
            from scoring.benchmark_engine import calculate_benchmark

            after_expl = calculate_explainable_score(st.session_state.rewritten_ad)

            if not after_expl.get("error"):
                after_score  = after_expl["total_score"]
                after_grade  = after_expl["grade"]
                before_score = expl["total_score"]
                improvement  = after_score - before_score
                imp_pct      = round(improvement / before_score * 100, 1) if before_score > 0 else 0

                # Color based on improvement
                imp_color = "#2ecc71" if improvement >= 10 else "#f39c12" if improvement >= 0 else "#e74c3c"

                ba1, ba2, ba3 = st.columns(3)

                with ba1:
                    st.markdown("**🔴 Original Score**")
                    st.markdown(
                        f'<div style="background:#e74c3c22; border:2px solid #e74c3c; '
                        f'border-radius:12px; padding:16px; text-align:center;">'                        f'<div style="font-size:2.5rem; font-weight:900; color:#e74c3c;">{before_score}</div>'                        f'<div style="color:#e74c3c; font-size:0.9rem;">{expl["grade"]}</div></div>',
                        unsafe_allow_html=True
                    )

                with ba2:
                    st.markdown("**🟢 Optimized Score**")
                    st.markdown(
                        f'<div style="background:#2ecc7122; border:2px solid #2ecc71; '
                        f'border-radius:12px; padding:16px; text-align:center;">'                        f'<div style="font-size:2.5rem; font-weight:900; color:#2ecc71;">{after_score}</div>'                        f'<div style="color:#2ecc71; font-size:0.9rem;">{after_grade}</div></div>',
                        unsafe_allow_html=True
                    )

                with ba3:
                    st.markdown("**📈 Improvement**")
                    imp_sign = "+" if improvement >= 0 else ""
                    st.markdown(
                        f'<div style="background:{imp_color}22; border:2px solid {imp_color}; '
                        f'border-radius:12px; padding:16px; text-align:center;">'                        f'<div style="font-size:2.5rem; font-weight:900; color:{imp_color};">{imp_sign}{improvement}</div>'                        f'<div style="color:{imp_color}; font-size:0.9rem;">{imp_sign}{imp_pct}%</div></div>',
                        unsafe_allow_html=True
                    )

                # Dimension comparison table
                st.markdown("**Dimension Comparison:**")
                dh1, dh2, dh3, dh4 = st.columns([3,1,1,1])
                dh1.markdown("**Dimension**")
                dh2.markdown("**Before**")
                dh3.markdown("**After**")
                dh4.markdown("**Change**")

                for bd in expl["dimensions"]:
                    dim_name = bd["dimension"]
                    b_score  = bd["score"]
                    a_score  = next(
                        (d["score"] for d in after_expl["dimensions"] if d["dimension"] == dim_name),
                        b_score
                    )
                    change   = a_score - b_score
                    dc1, dc2, dc3, dc4 = st.columns([3,1,1,1])
                    dc1.write(dim_name)
                    dc2.write(b_score)
                    dc3.write(a_score)
                    ch_str = "+{}".format(change) if change > 0 else str(change)
                    ch_col = "green" if change > 0 else "red" if change < 0 else "gray"
                    dc4.markdown(
                        f'<span style="color:{ch_col}; font-weight:600;">{ch_str}</span>',
                        unsafe_allow_html=True
                    )

            st.divider()

            # ── WORD DIFF ──
            st.markdown("### Word-level Changes")
            st.caption("🟢 Green = added words | 🔴 Red strikethrough = removed words")
            diff_html = generate_word_diff(
                st.session_state.original_ad,
                st.session_state.rewritten_ad
            )
            st.markdown(
                f'<div class="ad-box-new" style="line-height:2;">{diff_html}</div>',
                unsafe_allow_html=True
            )

            st.divider()

            # ── GAPS ──
            # ── MULTI-STRATEGY GENERATION ──
            st.divider()
            st.markdown("### Multi-Strategy Ad Generation")
            st.caption("Generate 3 different ad strategies in parallel. Uses 2x API credits.")

            if st.button("Generate 3 Strategies", type="primary", key="gen_strategies"):
                st.session_state.strategies = None

            if st.session_state.get("strategies") is None and st.session_state.get("gen_strategies_clicked"):
                with st.spinner("Generating 3 strategies in parallel..."):
                    from agents.strategy_builder import generate_all_strategies
                    st.session_state.strategies = generate_all_strategies(
                        original_ad=st.session_state.original_ad,
                        gaps=st.session_state.gaps
                    )

            # Trigger on button click
            if st.session_state.get("gen_strategies"):
                if st.session_state.strategies is None:
                    with st.spinner("Generating Conversion, Emotional, and Urgency strategies..."):
                        from agents.strategy_builder import generate_all_strategies
                        st.session_state.strategies = generate_all_strategies(
                            original_ad=st.session_state.original_ad,
                            gaps=st.session_state.gaps
                        )

            if st.session_state.strategies:
                multi = st.session_state.strategies
                strategies_list = multi["strategies"]

                # Winner banner
                winner_key = multi.get("winner_key")
                if winner_key:
                    winner = next((s for s in strategies_list if s["strategy_key"] == winner_key), None)
                    if winner:
                        st.success("🏆 Winner: {} — Score: {}/100".format(
                            winner["strategy_name"], winner["score"]
                        ))

                # 3 strategy cards
                cols = st.columns(3)
                for idx, strategy in enumerate(strategies_list):
                    with cols[idx]:
                        score     = strategy.get("score", 0) or 0
                        grade     = strategy.get("grade", "N/A")
                        is_winner = strategy.get("is_winner", False)
                        s_color   = "#2ecc71" if score >= 70 else "#f39c12" if score >= 50 else "#e74c3c"
                        border    = "3px solid #f1c40f" if is_winner else "1px solid {}".format(s_color)
                        winner_badge = " 🏆" if is_winner else ""

                        st.markdown(
                            f'<div style="border:{border}; border-radius:12px; padding:16px; margin-bottom:8px;">'                            f'<h4 style="margin:0; color:{s_color};">{strategy["strategy_icon"]} {strategy["strategy_name"]}{winner_badge}</h4>'                            f'<p style="color:#888; font-size:0.8rem; margin:4px 0;">{strategy["description"]}</p>'                            f'<div style="font-size:2rem; font-weight:900; color:{s_color}; text-align:center;">{score}</div>'                            f'<div style="text-align:center; color:{s_color}; font-size:0.9rem;">{grade}</div>'                            f'</div>',
                            unsafe_allow_html=True
                        )
                        st.markdown("**Ad Copy:**")
                        st.info(strategy["rewritten_ad"])
                        st.caption("Use when: {}".format(strategy["use_case"]))

                # Dimension comparison
                st.markdown("#### Dimension Comparison")
                dim_comp = multi.get("dimension_comparison", {})
                if dim_comp:
                    dh0, dh1, dh2, dh3 = st.columns([3,1,1,1])
                    dh0.markdown("**Dimension**")
                    dh1.markdown("**🎯 Conv.**")
                    dh2.markdown("**❤️ Emot.**")
                    dh3.markdown("**⏰ Urg.**")
                    for dim, scores in dim_comp.items():
                        dc0, dc1, dc2, dc3 = st.columns([3,1,1,1])
                        dc0.write(dim)
                        dc1.write(scores.get("Conversion", "-"))
                        dc2.write(scores.get("Emotional", "-"))
                        dc3.write(scores.get("Urgency", "-"))

                # Recommendation
                st.markdown("**💡 Recommendation:**")
                st.info(multi["recommendation"])

            st.divider()
            st.markdown("### Gaps Identified")
            gaps = st.session_state.gaps
            if gaps:
                for gap in gaps:
                    sev   = gap.get("severity", "medium").lower()
                    color = {"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"}.get(sev, "#888")
                    icon  = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                    st.markdown(
                        f'<div style="border-left:4px solid {color}; padding:12px; '                        f'margin-bottom:12px; background:{color}11; border-radius:0 8px 8px 0;">'                        f'<strong>{icon} [{sev.upper()}] {gap.get("gap","")}</strong><br>'                        f'<span style="color:#888;">Competitors do: {gap.get("competitor_does","")}</span></div>',
                        unsafe_allow_html=True
                    )

            # ── CHANGES MADE ──
            st.divider()
            st.markdown("### Changes Made by AI")
            changes = st.session_state.changes_made
            if changes:
                for line in changes.split("\n"):
                    line = line.strip()
                    if line.startswith("-"):
                        st.markdown(f"• {line[1:].strip()}")
                    elif line:
                        st.markdown(line)

with tab3:
    st.markdown('<p class="section-header">Analysis History</p>', unsafe_allow_html=True)

    if not st.session_state.history:
        st.info("No analyses yet — run your first analysis in Tab 1.")

    else:
        st.caption(f"Showing last {len(st.session_state.history)} analyses (this session)")

        for i, entry in enumerate(st.session_state.history):
            col_a, col_b, col_c = st.columns([4, 1, 1])

            with col_a:
                st.markdown(f"""
                <div class="history-card">
                    <strong>{entry['product']}</strong><br>
                    <span style="color:#888; font-size:0.85rem;">{entry['original']}</span>
                </div>
                """, unsafe_allow_html=True)

            with col_b:
                # Color based on score
                color = "#22C55E" if entry["score"] >= 70 else "#F59E0B" if entry["score"] >= 50 else "#EF4444"
                st.markdown(
                    f'<div style="font-size:1.8rem; font-weight:700; color:{color}; text-align:center;">'
                    f'{entry["score"]}</div>',
                    unsafe_allow_html=True
                )

            with col_c:
                st.markdown(
                    f'<div style="color:#888; font-size:0.8rem; text-align:center; margin-top:0.5rem;">'
                    f'{entry["timestamp"]}</div>',
                    unsafe_allow_html=True
                )

        if st.button("Clear History"):
            st.session_state.history = []
            st.rerun()
            # st.rerun() — page reload karo
            # History cleared — empty state dikhega


# ============================================================
# TAB 4 — EXPORT
# ============================================================
with tab4:
    if not st.session_state.analysis_done:
        st.info("👆 Run analysis in Tab 1 first.")

    else:
        st.markdown('<p class="section-header">Export Analysis Report</p>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Viral Score", f"{st.session_state.score_data['total_score']}/100")
        col2.metric("Gaps Found",  len(st.session_state.gaps))
        col3.metric("Grade",       st.session_state.score_data["grade"].split("—")[0].strip())

        st.divider()

        if st.button("📄 Generate PDF Report", type="primary", use_container_width=True):
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_report(
                    product_description = st.session_state.product_desc,
                    original_ad         = st.session_state.original_ad,
                    score_data          = st.session_state.score_data,
                    gaps                = st.session_state.gaps,
                    rewritten_ad        = st.session_state.rewritten_ad,
                    changes_made        = st.session_state.changes_made
                )

            st.download_button(
                label            = "⬇️ Download PDF Report",
                data             = pdf_bytes,
                file_name        = "ad_genius_report.pdf",
                mime             = "application/pdf",
                use_container_width = True
            )
            st.success("PDF ready!")