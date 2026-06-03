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
from scoring.scorer    import calculate_viral_score
from agents.builder    import run_full_pipeline
from rag.retriever     import get_similar_ads
from utils.pdf_exporter import generate_report
from utils.logger      import app_logger

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title = "Ad Genius Pro",
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
st.markdown('<p class="main-header">🎯 Ad Genius Pro</p>', unsafe_allow_html=True)
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
    """
    original_words  = original.split()
    rewritten_words = rewritten.split()

    # Find words only in original — removed
    original_set  = set(w.lower().strip(".,!?") for w in original_words)
    rewritten_set = set(w.lower().strip(".,!?") for w in rewritten_words)

    removed_words = original_set - rewritten_set
    # Set difference — words in original but not in rewritten

    added_words   = rewritten_set - original_set
    # Words in rewritten but not in original

    # Build highlighted HTML for rewritten ad
    html_parts = []
    for word in rewritten_words:
        clean = word.lower().strip(".,!?")
        if clean in added_words:
            html_parts.append(
                f'<span class="word-added">{word}</span>'
            )
        else:
            html_parts.append(word)

    return " ".join(html_parts)


# ============================================================
# HELPER: Save to history
# NEW: Pehle nahi tha
# WHAT: Analysis result history mein save karo
# WHERE: Successful analysis ke baad call hota hai
# WHY: User last 5 analyses compare kar sake
# ============================================================
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

        status.info("📊 Step 2/3 — Calculating viral score...")
        with st.spinner(""):
            score_data = calculate_viral_score(ad_draft)

            if score_data.get("error"):
                st.error(f"Scoring error: {score_data['error_msg']}")
                app_logger.error(f"Scoring failed: {score_data['error_msg']}")
                st.stop()

            st.session_state.score_data = score_data

        status.info("🤖 Step 3/3 — Running 2-agent analysis...")
        with st.spinner(""):
            pipeline = run_full_pipeline(ad_draft, product_desc)

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
        col_score, col_breakdown = st.columns([1, 2])

        with col_score:
            # NEW: Visual score card
            score = st.session_state.score_data["total_score"]
            grade = st.session_state.score_data["grade"]

            st.markdown(f"""
            <div class="score-container">
                <div class="score-number">{score}</div>
                <div class="score-grade">{grade}</div>
                <div style="color:rgba(255,255,255,0.7); font-size:0.8rem; margin-top:0.5rem;">
                    out of 100
                </div>
            </div>
            """, unsafe_allow_html=True)

            wc = st.session_state.score_data["word_count"]
            st.caption(f"Word count: {wc} words")

        with col_breakdown:
            st.markdown('<p class="section-header">Score Breakdown</p>', unsafe_allow_html=True)

            breakdown = st.session_state.score_data["breakdown"]
            labels = {
                "hook_strength":       "🎣 Hook Strength",
                "clarity":             "💡 Clarity",
                "keyword_density":     "🔑 Keyword Density",
                "sentiment_stability": "😊 Sentiment Stability",
                "length_score":        "📏 Length Score",
            }

            for key, label in labels.items():
                val = breakdown[key]
                col_a, col_b = st.columns([3, 1])
                col_a.write(label)
                col_b.write(f"**{val}/10**")
                st.progress(val / 10)

        st.divider()

        # Gaps section
        st.markdown('<p class="section-header">Gaps Identified</p>', unsafe_allow_html=True)

        high_gaps   = [g for g in st.session_state.gaps if g["severity"] == "high"]
        medium_gaps = [g for g in st.session_state.gaps if g["severity"] == "medium"]
        low_gaps    = [g for g in st.session_state.gaps if g["severity"] == "low"]

        for gap in high_gaps:
            st.markdown(f"""
            <div class="gap-high">
                <div class="gap-title">🔴 [HIGH] {gap['gap']}</div>
                <div class="gap-sub">Competitors do: {gap['competitor_does']}</div>
            </div>
            """, unsafe_allow_html=True)

        for gap in medium_gaps:
            st.markdown(f"""
            <div class="gap-medium">
                <div class="gap-title">🟡 [MEDIUM] {gap['gap']}</div>
                <div class="gap-sub">Competitors do: {gap['competitor_does']}</div>
            </div>
            """, unsafe_allow_html=True)

        for gap in low_gaps:
            st.markdown(f"""
            <div class="gap-low">
                <div class="gap-title">🟢 [LOW] {gap['gap']}</div>
                <div class="gap-sub">Competitors do: {gap['competitor_does']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # NEW: Side by side with word diff
        st.markdown('<p class="section-header">Original vs Optimized</p>', unsafe_allow_html=True)

        col_orig, col_new = st.columns(2)

        with col_orig:
            st.markdown("**❌ Original Ad**")
            st.markdown(
                f'<div class="ad-box-original">{st.session_state.original_ad}</div>',
                unsafe_allow_html=True
            )

        with col_new:
            st.markdown("**✅ Optimized Ad**")
            st.markdown(
                f'<div class="ad-box-new">{st.session_state.rewritten_ad}</div>',
                unsafe_allow_html=True
            )

        # NEW: Word diff section
        st.markdown('<p class="section-header">Word-level Changes</p>', unsafe_allow_html=True)
        st.caption("🟩 Green = added words &nbsp;&nbsp; 🟥 Red strikethrough = removed words")

        diff_html = generate_word_diff(
            st.session_state.original_ad,
            st.session_state.rewritten_ad
        )
        st.markdown(
            f'<div class="ad-box-new" style="line-height:2;">{diff_html}</div>',
            unsafe_allow_html=True
        )

        st.divider()

        st.markdown('<p class="section-header">Changes Made</p>', unsafe_allow_html=True)
        st.write(st.session_state.changes_made)


# ============================================================
# TAB 3 — HISTORY — NEW TAB
# WHAT: Last 5 analyses ki summary
# WHY: User compare kar sake — progress dekhe
# ============================================================
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