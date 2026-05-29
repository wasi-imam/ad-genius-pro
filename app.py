# app.py
# Purpose: Main Streamlit application — the user interface.
# Entry point: streamlit run app.py
# All backend modules are imported and orchestrated here.

import streamlit as st
# streamlit — web UI library
# st.* functions automatically render in browser

from scoring.scorer   import calculate_viral_score
from agents.builder   import run_full_pipeline
from rag.retriever    import get_similar_ads
from utils.pdf_exporter import generate_report

# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Ad Genius Pro",
    page_icon="🎯",
    layout="wide",
    # wide — full browser width use karo
    # centered — narrow column (default)
)

# ==========================================
# CUSTOM CSS
# ==========================================

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #534AB7;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #888;
        text-align: center;
        margin-bottom: 2rem;
    }
    .score-big {
        font-size: 4rem;
        font-weight: 700;
        color: #534AB7;
        text-align: center;
    }
    .gap-high   { color: #DC3545; font-weight: 600; }
    .gap-medium { color: #FFC107; font-weight: 600; }
    .gap-low    { color: #28A745; font-weight: 600; }
    .stProgress > div > div {
        background-color: #534AB7;
    }
</style>
""", unsafe_allow_html=True)
# unsafe_allow_html=True — HTML/CSS inject karne ki permission
# By default Streamlit HTML escape karta hai — yeh override karta hai

# ==========================================
# HEADER
# ==========================================

st.markdown('<p class="main-header">🎯 Ad Genius Pro</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">AI-powered ad optimization using RAG pipeline and multi-agent critique</p>', unsafe_allow_html=True)

st.divider()
# Horizontal line

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================

# Session state — Streamlit reruns entire script on every interaction
# Variables defined normally would reset each time
# st.session_state persists values across reruns

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "score_data"    not in st.session_state:
    st.session_state.score_data    = None

if "gaps"          not in st.session_state:
    st.session_state.gaps          = None

if "rewritten_ad"  not in st.session_state:
    st.session_state.rewritten_ad  = None

if "changes_made"  not in st.session_state:
    st.session_state.changes_made  = None

if "original_ad"   not in st.session_state:
    st.session_state.original_ad   = None

if "product_desc"  not in st.session_state:
    st.session_state.product_desc  = None

if "similar_ads"   not in st.session_state:
    st.session_state.similar_ads   = None

# ==========================================
# THREE TABS
# ==========================================

tab1, tab2, tab3 = st.tabs([
    "📝  Input & Competitor Insights",
    "⚡  Ad Critique & Rewrite",
    "📥  Export Report"
])
# st.tabs — creates tabbed interface
# Returns tab objects — use as context managers (with tab1:)

# ==========================================
# TAB 1 — INPUT & COMPETITOR INSIGHTS
# ==========================================

with tab1:
    st.subheader("Your Ad Details")

    col1, col2 = st.columns([1, 1])
    # st.columns — side by side layout
    # [1, 1] — equal width columns
    # [2, 1] would make left column twice as wide

    with col1:
        product_desc = st.text_input(
            label="Product Description",
            placeholder="e.g. premium running shoes for athletes",
            help="This is used to find similar competitor ads"
            # help — small tooltip/hint text
        )

        ad_draft = st.text_area(
            label="Your Ad Draft",
            placeholder="e.g. Great shoes. Buy now.",
            height=150,
            help="The ad copy you want to analyze and improve"
        )

    with col2:
        st.markdown("#### Or upload a competitor PDF")
        uploaded_file = st.file_uploader(
            label="Upload PDF (optional)",
            type=["pdf"],
            help="Large files are processed in memory-safe streaming batches"
        )

        if uploaded_file is not None:
            file_mb = uploaded_file.size / (1024 * 1024)
            # Convert bytes to megabytes
            st.caption(f"File size: {file_mb:.1f} MB")

            if st.button("Process PDF", type="secondary"):
                from rag.pdf_ingestion import process_pdf_streaming
                # Import here — only when needed

                progress_bar = st.progress(0)
                status_text  = st.empty()
                # st.empty() — placeholder that can be updated

                def update_progress(pct, msg):
                    progress_bar.progress(pct)
                    status_text.text(msg)

                with st.spinner("Processing PDF in streaming batches..."):
                    result = process_pdf_streaming(uploaded_file, update_progress)

                progress_bar.progress(1.0)
                status_text.text("Complete!")
                st.success(
                    f"Indexed {result['total_chunks']} chunks "
                    f"from {result['total_pages']} pages "
                    f"in {result['batches']} batches"
                )

    st.divider()

    # Analyze button
    analyze_clicked = st.button(
        label="🔍 Analyze My Ad",
        type="primary",
        use_container_width=True
        # use_container_width — button full width leta hai
    )

    if analyze_clicked:
        # Input validation
        if not product_desc.strip():
            st.error("Please enter a product description.")
            st.stop()
            # st.stop() — script execution rokta hai

        if not ad_draft.strip():
            st.error("Please enter your ad draft.")
            st.stop()

        # Run all three pipelines
        with st.spinner("Finding similar competitor ads..."):
            similar_ads = get_similar_ads(product_desc, n_results=5)
            st.session_state.similar_ads  = similar_ads
            st.session_state.product_desc = product_desc
            st.session_state.original_ad  = ad_draft

        with st.spinner("Calculating viral score..."):
            score_data = calculate_viral_score(ad_draft)
            st.session_state.score_data = score_data

        with st.spinner("Running 2-agent analysis and rewrite..."):
            pipeline_result = run_full_pipeline(ad_draft, product_desc)
            st.session_state.gaps         = pipeline_result["gaps"]
            st.session_state.rewritten_ad = pipeline_result["rewritten_ad"]
            st.session_state.changes_made = pipeline_result["changes_made"]
            st.session_state.analysis_done = True

        st.success("Analysis complete! See results in the next tabs.")

    # Show competitor ads if analysis done
    if st.session_state.similar_ads:
        st.subheader("Top Competitor Ads Found")
        st.caption("These are the most similar ads from our database")

        for ad in st.session_state.similar_ads:
            with st.expander(
                f"{ad['brand']} — {ad['similarity_score']:.0%} similar | {ad['platform']}"
            ):
                st.write(ad["ad_copy"])
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Hook",      ad["hook"][:40])
                col_b.metric("Sentiment", ad["sentiment"])
                col_c.metric("Has CTA",   ad["has_cta"])
                # st.metric — displays a labeled value

# ==========================================
# TAB 2 — AD CRITIQUE & REWRITE
# ==========================================

with tab2:
    if not st.session_state.analysis_done:
        st.info("Please run analysis in Tab 1 first.")
        # st.info — blue info box

    else:
        # ---- Viral Score Section ----
        st.subheader("Viral Score")

        score = st.session_state.score_data["total_score"]
        grade = st.session_state.score_data["grade"]

        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown(f'<p class="score-big">{score}</p>', unsafe_allow_html=True)
            st.markdown(f"<p style='text-align:center; font-size:1.2rem;'>{grade}</p>",
                       unsafe_allow_html=True)
            st.caption(f"Word count: {st.session_state.score_data['word_count']}")

        with col2:
            st.markdown("**Score Breakdown**")
            breakdown = st.session_state.score_data["breakdown"]

            metrics_labels = {
                "length_score":        "Length Score",
                "hook_strength":       "Hook Strength",
                "sentiment_stability": "Sentiment Stability",
                "keyword_density":     "Keyword Density",
                "clarity":             "Clarity"
            }

            for key, label in metrics_labels.items():
                value = breakdown[key]
                st.write(f"**{label}:** {value}/10")
                st.progress(value / 10)
                # st.progress expects 0.0 to 1.0
                # value/10 converts 1-10 to 0.1-1.0

        st.divider()

        # ---- Gaps Section ----
        st.subheader(f"Gaps Identified — {len(st.session_state.gaps)} found")

        for gap in st.session_state.gaps:
            severity = gap["severity"]

            if severity == "high":
                st.error(f"🔴 **[HIGH]** {gap['gap']}")
            elif severity == "medium":
                st.warning(f"🟡 **[MEDIUM]** {gap['gap']}")
            else:
                st.success(f"🟢 **[LOW]** {gap['gap']}")
            # st.error   — red box
            # st.warning — yellow box
            # st.success — green box

            st.caption(f"Competitors do: {gap['competitor_does']}")

        st.divider()

        # ---- Side by Side Comparison ----
        st.subheader("Original vs Optimized")

        col_orig, col_new = st.columns(2)

        with col_orig:
            st.markdown("**Original Ad**")
            st.error(st.session_state.original_ad)
            # Red box — needs improvement

        with col_new:
            st.markdown("**Optimized Ad**")
            st.success(st.session_state.rewritten_ad)
            # Green box — improved version

        st.divider()

        # ---- Changes Made ----
        st.subheader("Changes Made")
        st.write(st.session_state.changes_made)

# ==========================================
# TAB 3 — EXPORT REPORT
# ==========================================

with tab3:
    if not st.session_state.analysis_done:
        st.info("Please run analysis in Tab 1 first.")

    else:
        st.subheader("Download Your Report")
        st.write("Export a complete PDF report with score breakdown, gaps, and optimized ad copy.")

        # Summary stats before download
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Viral Score",
            f"{st.session_state.score_data['total_score']}/100"
        )
        col2.metric(
            "Gaps Found",
            len(st.session_state.gaps)
        )
        col3.metric(
            "New Word Count",
            st.session_state.score_data["word_count"]
        )

        st.divider()

        # Generate and download PDF
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
                label="⬇️ Download PDF Report",
                data=pdf_bytes,
                file_name="ad_genius_report.pdf",
                mime="application/pdf",
                use_container_width=True
                # mime — file type batata hai browser ko
                # "application/pdf" — browser PDF ki tarah treat karega
            )
            st.success("PDF ready! Click the button above to download.")