import streamlit as st
import pandas as pd
from datetime import datetime

from database import DatabaseManager
from scraper import ScraperEngine
from analytics import AnalyticsEngine
from filters import HeadlineFilter

# Configure the Streamlit page
st.set_page_config(
    page_title="NewsScrape Pro Web",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize backend services (cached so they aren't recreated on every button click)
@st.cache_resource
def get_backend():
    db = DatabaseManager()
    scraper = ScraperEngine()
    analytics = AnalyticsEngine(dark_mode=True)
    return db, scraper, analytics

db, scraper, analytics = get_backend()

# Sidebar Navigation
st.sidebar.title("NewsScrape Pro 📰")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", ["Dashboard", "Scraper", "Database", "Analytics", "About"])

# ---------------------------------------------------------
# PAGE 1: DASHBOARD
# ---------------------------------------------------------
if page == "Dashboard":
    st.title("📊 Dashboard")
    
    stats = db.get_statistics()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Total Headlines", value=stats.get("total_headlines", 0))
    with col2:
        st.metric(label="Today's Headlines", value=stats.get("today_headlines", 0))
    with col3:
        st.metric(label="Total Sources", value=stats.get("total_sources", 0))
    with col4:
        last = stats.get("last_scraped", "Never")
        if last and last != "Never":
            last = last[:16].replace("T", " ")
        st.metric(label="Last Scraped", value=last)
        
    st.markdown("### Recent Headlines")
    recent = db.get_all_headlines(limit=10)
    if recent:
        df = pd.DataFrame(recent)[["source", "title", "published_time", "url"]]
        # Make URLs clickable in Streamlit dataframe
        st.dataframe(
            df,
            column_config={"url": st.column_config.LinkColumn("Article URL")},
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No headlines in database. Go to the Scraper page to get some!")

# ---------------------------------------------------------
# PAGE 2: SCRAPER
# ---------------------------------------------------------
elif page == "Scraper":
    st.title("🕷️ Web Scraper")
    st.write("Run the scraper to collect the latest headlines from configured news sources.")
    
    available_sources = scraper.get_source_names()
    
    # Multiselect for sources
    selected_sources = st.multiselect(
        "Select Sources to Scrape:",
        options=available_sources,
        default=available_sources
    )
    
    if st.button("Start Scraping", type="primary"):
        if not selected_sources:
            st.warning("Please select at least one source.")
        else:
            with st.spinner(f"Scraping {len(selected_sources)} sources... This may take a minute."):
                # We don't use the progress callback in streamlit to keep it simple, just run it
                results = scraper.scrape_selected(selected_sources)
                if results:
                    inserted, skipped = db.insert_many(results)
                    db.log_activity("web_scrape", f"{inserted} new, {skipped} dupes")
                    st.success(f"Scrape complete! Found {len(results)} headlines ({inserted} new, {skipped} duplicates skipped).")
                else:
                    st.error("Scrape failed or returned zero results.")

# ---------------------------------------------------------
# PAGE 3: DATABASE (Search & Filter)
# ---------------------------------------------------------
elif page == "Database":
    st.title("🗄️ Database & Search")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("Search keywords...")
    with col2:
        source_filter = st.selectbox("Source", ["All"] + db.get_distinct_sources())
    with col3:
        cat_filter = st.selectbox("Category", ["All"] + db.get_distinct_categories())
        
    src = source_filter if source_filter != "All" else None
    cat = cat_filter if cat_filter != "All" else None
    
    results = db.search(keyword=search_query, source=src, category=cat, limit=500)
    
    if results:
        st.write(f"Found **{len(results)}** matching headlines.")
        df = pd.DataFrame(results)[["title", "source", "category", "author", "published_time", "url"]]
        st.dataframe(
            df,
            column_config={
                "url": st.column_config.LinkColumn("URL"),
                "title": st.column_config.TextColumn("Headline Title", width="large")
            },
            hide_index=True,
            use_container_width=True,
            height=600
        )
    else:
        st.info("No matching headlines found.")

# ---------------------------------------------------------
# PAGE 4: ANALYTICS
# ---------------------------------------------------------
elif page == "Analytics":
    st.title("📈 Analytics")
    
    src_data = db.get_headlines_per_source()
    cat_data = db.get_category_distribution()
    daily_data = db.get_daily_activity(30)
    
    if not src_data:
        st.info("Not enough data to generate charts. Run the scraper first!")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.pyplot(analytics.headlines_per_source(src_data))
            st.pyplot(analytics.daily_activity(daily_data))
            
        with col2:
            st.pyplot(analytics.category_distribution(cat_data))
            st.pyplot(analytics.weekly_trend(daily_data))

# ---------------------------------------------------------
# PAGE 5: ABOUT
# ---------------------------------------------------------
elif page == "About":
    st.title("ℹ️ About NewsScrape Pro")
    st.write("Advanced Multi-Source News Headline Scraper built for portfolio demonstration.")
    
    st.markdown("### Technologies Used")
    st.markdown("- **Backend:** Python, BeautifulSoup4, SQLite3")
    st.markdown("- **Frontend:** Streamlit (Web), CustomTkinter (Desktop)")
    st.markdown("- **Data Processing:** Pandas, Matplotlib")
    
    st.markdown("### Connect with the Developer")
    st.markdown("[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/sohamfegade)")
    st.markdown("[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/sohamfegade)")
