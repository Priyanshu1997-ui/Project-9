# app.py
import streamlit as st
from dotenv import load_dotenv
import logging
from typing import Optional

# load .env (for API keys)
load_dotenv()

# Import helpers from langchain_config
from langchain_config import (
    get_summary,
    get_summary_cached_module,
    get_news_articles,
    summarize_articles_llm,
    estimate_tokens,
    clear_module_cache,
)

# ------------------ Streamlit page config & logger ------------------------
st.set_page_config(page_title="Equity Research News Tool", layout="wide")
st.title("Equity Research News Tool")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# ------------------ Sidebar (options) ------------------------------------
with st.sidebar:
    st.markdown("## Options")
    max_articles = st.slider(
        "Max articles to fetch", min_value=5, max_value=100, value=20, step=5
    )
    # date inputs (optional) — these can be passed later if you add date support in langchain_config.get_news_articles
    date_from = st.date_input("From (optional)", value=None)
    date_to = st.date_input("To (optional)", value=None)

    st.markdown("---")
    cache_ttl_minutes = st.number_input(
        "Cache TTL (minutes, st.cache_data)", min_value=1, max_value=1440, value=60
    )
    st.write("Tip: keep `max articles` low while developing to save tokens.")
    st.markdown("---")

    if st.button("Clear all caches"):
        # Clear Streamlit cache and module-level LRU cache
        try:
            st.cache_data.clear()
        except Exception:
            pass
        clear_module_cache()
        st.success("Cleared Streamlit cache and module cache.")


@st.cache_data(ttl=60 * 60 * 24)  # default 24 hours; we also control via UI below by manual clear
def get_summary_cached_ui(query: str, max_articles: int) -> str:
    # This calls the module-level cached wrapper which itself uses lru_cache
    return get_summary_cached_module(query, max_articles)


# ------------------ Main UI ----------------------------------------------
query = st.text_input("Enter query (company name, sector, event…)", value="", key="query_input")

col1, col2 = st.columns([3, 1])
with col2:
    if st.button("Run (Get News Summary)"):
        run_pressed = True
    else:
        run_pressed = False

# Run on button press
if run_pressed:
    if not query.strip():
        st.warning("Please enter a query.")
    else:
        # Show fetched articles first, then summarize (helps verify NewsAPI working)
        try:
            with st.spinner("Fetching articles from NewsAPI..."):
                # Try to pass date filters if your get_news_articles supports them; currently pass only max_articles
                articles = get_news_articles(query, max_articles=max_articles)
        except Exception as e:
            st.error(f"Failed to fetch articles: {e}")
            logger.exception("NewsAPI fetch failed")
            articles = []

        if not articles:
            st.info("No articles found for this query.")
        else:
            st.markdown(f"### Fetched articles ({len(articles)})")
            # Show a compact list with links (if url present)
            for a in articles[:min(len(articles), 30)]:
                title = a.get("title") or "<no title>"
                src = a.get("source", {}).get("name") if a.get("source") else a.get("source")
                url = a.get("url")
                if url:
                    st.write(f"- [{title}]({url}) — *{src}*")
                else:
                    st.write(f"- {title} — *{src}*")

    
            
            concat_text = "\n\n".join(
                [(a.get("title") or "") + " — " + (a.get("description") or "") for a in articles]
            )
            try:
                tokens_est = estimate_tokens(concat_text)
                st.info(f"Estimated tokens for input (approx): {tokens_est}")
                if tokens_est > 8000:
                    st.warning(
                        "Large token estimate — consider lowering max articles to reduce OpenAI usage/cost."
                    )
            except Exception:
                
                pass

            # Summarize (cached)
            try:
                with st.spinner("Summarizing (calls LLM)..."):
                    
                    
                    summary = get_summary_cached_ui(query, max_articles)
            except Exception as e:
                st.error(f"Error during summarization: {e}")
                logger.exception("Summarization error")
                summary = None

            if summary:
                st.markdown("### Summary")
                st.write(summary)
                st.download_button(
                    "Download summary (txt)", data=summary, file_name="summary.txt"
                )

                # Save to in-session history
                if "history" not in st.session_state:
                    st.session_state.history = []
                st.session_state.history.insert(0, {"query": query, "summary": summary})

# Recent queries & history
if "history" in st.session_state and st.session_state.history:
    st.markdown("### Recent queries")
    for i, h in enumerate(st.session_state.history[:10]):
        st.write(f"**{h['query']}**")
        st.write(h["summary"][:300] + ("..." if len(h["summary"]) > 300 else ""))

# Debug / developer utilities
with st.expander("Developer tools (debug)"):
    st.write("Use these when developing to inspect/clear caches.")
    if st.button("Clear Streamlit cache only"):
        try:
            st.cache_data.clear()
            st.success("Cleared Streamlit cache.")
        except Exception:
            st.error("Failed to clear Streamlit cache.")
    st.write("Module-level cached function available: get_summary_cached_module(query, max_articles)")

# Footer
st.markdown("---")
st.markdown(
    "Notes: This tool uses NewsAPI (developer key limits apply) and OpenAI (token costs). "
    "Keep `max articles` low during development to reduce cost."
)
