"""Daily Menu - Lunch Recommendation System."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar

from database import load_restaurants, load_history, add_visit, delete_visit, update_restaurant_data
from recommender import (
    get_recommendation,
    get_all_recommendations,
    explain_recommendation,
    get_monthly_stats,
    get_month_visits,
    is_work_day,
    is_thursday,
    get_day_name,
)


st.set_page_config(
    page_title="Daily Menu",
    page_icon="🍽️",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    .recommendation-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 1rem;
    }
    .stat-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .status-green { color: #28a745; }
    .status-yellow { color: #ffc107; }
    .status-red { color: #dc3545; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "restaurants" not in st.session_state:
        st.session_state.restaurants = load_restaurants()
    if "history" not in st.session_state:
        st.session_state.history = load_history()


def refresh_data():
    """Reload data from sources."""
    st.session_state.restaurants = load_restaurants()
    st.session_state.history = load_history()


def render_sidebar():
    """Render sidebar with stats and actions."""
    st.sidebar.title("Daily Menu")
    st.sidebar.caption("Lunch Recommendation System")

    # Today info
    today = datetime.now()
    day_name = get_day_name(today)

    if day_name:
        st.sidebar.info(f"Today: {day_name}, {today.strftime('%B %d')}")
        if is_thursday(today):
            st.sidebar.success("It's Thursday! No budget limit today.")
    else:
        st.sidebar.warning("It's the weekend! Enjoy your time off.")

    st.sidebar.divider()

    # Monthly stats
    st.sidebar.subheader("This Month")
    stats = get_monthly_stats(st.session_state.history)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Days Visited", stats["days_visited"])
    with col2:
        st.metric("Total Spent", f"{stats['total_spent']} SAR")

    # Average with color indicator
    avg = stats["current_average"]
    status = stats["status"]
    status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[status]

    st.sidebar.metric(
        "Daily Average",
        f"{avg} SAR",
        delta=f"Target: 22.5 SAR",
        delta_color="off"
    )
    st.sidebar.caption(f"{status_emoji} Status: {'On Track' if status == 'green' else 'Warning' if status == 'yellow' else 'Over Budget'}")

    st.sidebar.divider()

    # Actions
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        refresh_data()
        st.rerun()


def render_recommendation_tab():
    """Render today's pick tab."""
    st.header("Today's Pick")

    today = datetime.now()

    if not is_work_day(today):
        st.info("It's the weekend! Enjoy your time off. Come back on Sunday.")
        return

    recommendation = get_recommendation(
        st.session_state.restaurants,
        st.session_state.history,
        today
    )

    if not recommendation:
        st.warning("No restaurants available for today. Add some restaurants first!")
        return

    # Main recommendation card
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"🍽️ {recommendation['name']}")
        st.caption(f"📍 {recommendation['area']}")

        cols = st.columns(3)
        with cols[0]:
            st.metric("Item", recommendation["item"])
        with cols[1]:
            st.metric("Price", f"{recommendation['price']} SAR")
        with cols[2]:
            st.metric("Travel Time", f"{recommendation['travel_time']} min")

        # Explanation
        explanation = explain_recommendation(recommendation, st.session_state.history, today)
        st.info(f"**Why this?** {explanation}")

    with col2:
        st.subheader("Quick Actions")

        if st.button("✅ Accept & Log Visit", use_container_width=True, type="primary"):
            success = add_visit(
                recommendation["name"],
                recommendation["price"],
                recommendation["item"]
            )
            if success:
                st.success("Visit logged!")
                refresh_data()
                st.rerun()
            else:
                st.error("Failed to log visit.")

    # Alternative options
    st.divider()
    st.subheader("Other Options")

    alternatives = get_all_recommendations(
        st.session_state.restaurants,
        st.session_state.history,
        today,
        limit=5
    )

    if len(alternatives) > 1:
        for alt in alternatives[1:]:  # Skip first (it's the main recommendation)
            with st.expander(f"{alt['name']} - {alt['price']} SAR"):
                st.write(f"**Item:** {alt['item']}")
                st.write(f"**Area:** {alt['area']}")
                st.write(f"**Travel:** {alt['travel_time']} min")

                if st.button(f"Log {alt['name']}", key=f"alt_{alt['name']}"):
                    add_visit(alt["name"], alt["price"], alt["item"])
                    refresh_data()
                    st.rerun()


def render_month_tab():
    """Render this month's overview tab."""
    st.header("This Month")

    today = datetime.now()
    visits = get_month_visits(st.session_state.history)
    stats = get_monthly_stats(st.session_state.history)

    # Stats row
    cols = st.columns(4)
    with cols[0]:
        st.metric("Visits", stats["days_visited"])
    with cols[1]:
        st.metric("Total Spent", f"{stats['total_spent']} SAR")
    with cols[2]:
        st.metric("Average", f"{stats['current_average']} SAR")
    with cols[3]:
        remaining_days = 22 - stats["days_visited"]
        if remaining_days > 0:
            budget_left = (22 * 22.5) - stats["total_spent"]
            daily_budget = budget_left / remaining_days if remaining_days > 0 else 0
            st.metric("Remaining Budget/Day", f"{daily_budget:.0f} SAR")
        else:
            st.metric("Remaining Days", "0")

    st.divider()

    # Calendar view
    st.subheader("Visit Calendar")

    # Create calendar data
    cal = calendar.Calendar(firstweekday=6)  # Week starts Sunday
    month_days = cal.monthdayscalendar(today.year, today.month)

    # Map visits to dates
    visit_map = {}
    for v in visits:
        date = v["date"].split("-")[2].lstrip("0")
        visit_map[int(date)] = v

    # Render calendar
    cols = st.columns(7)
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for i, day in enumerate(days):
        cols[i].write(f"**{day}**")

    for week in month_days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
            elif day in visit_map:
                v = visit_map[day]
                cols[i].success(f"{day}\n{v['price']} SAR")
            else:
                cols[i].write(str(day))

    st.divider()

    # Spending chart
    if visits:
        st.subheader("Daily Spending")

        df = pd.DataFrame(visits)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        st.bar_chart(df.set_index("date")["price"])

        # Running average
        df["running_avg"] = df["price"].expanding().mean()
        st.line_chart(df.set_index("date")["running_avg"])


def render_history_tab():
    """Render full history tab."""
    st.header("Visit History")

    history = st.session_state.history
    visits = history.get("visits", [])

    if not visits:
        st.info("No visits recorded yet. Log your first visit from Today's Pick!")
        return

    # Create DataFrame
    df = pd.DataFrame(visits)
    df = df.sort_values("date", ascending=False)

    # Search filter
    search = st.text_input("Search restaurants", "")
    if search:
        df = df[df["restaurant"].str.contains(search, case=False)]

    # Display with delete option
    for idx, row in df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])

        with col1:
            st.write(row["date"])
        with col2:
            st.write(row["restaurant"])
        with col3:
            st.write(row["item"])
        with col4:
            st.write(f"{row['price']} SAR")
        with col5:
            if st.button("🗑️", key=f"del_{row['date']}_{row['restaurant']}"):
                delete_visit(row["date"], row["restaurant"])
                refresh_data()
                st.rerun()

    # Summary
    st.divider()
    total = df["price"].sum()
    avg = df["price"].mean()
    st.write(f"**Total visits:** {len(df)} | **Total spent:** {total} SAR | **Average:** {avg:.1f} SAR")


def render_restaurants_tab():
    """Render restaurants management tab."""
    st.header("Restaurants")

    restaurants = st.session_state.restaurants

    # Add new restaurant form
    with st.expander("➕ Add New Restaurant"):
        with st.form("add_restaurant"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Restaurant Name")
                area = st.text_input("Area")
                item = st.text_input("Recommended Item")

            with col2:
                price = st.number_input("Estimated Price (SAR)", min_value=0, max_value=100, value=20)
                travel_time = st.number_input("Travel Time (minutes)", min_value=0, max_value=120, value=20)
                specific_day = st.selectbox("Specific Day", ["", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])

            if st.form_submit_button("Add Restaurant"):
                if name and area and item:
                    new_row = pd.DataFrame([{
                        "name": name,
                        "area": area,
                        "specific_day": specific_day,
                        "item": item,
                        "travel_time": travel_time,
                        "price": price,
                    }])
                    st.session_state.restaurants = pd.concat([restaurants, new_row], ignore_index=True)
                    update_restaurant_data(st.session_state.restaurants)
                    st.success(f"Added {name}!")
                    st.rerun()
                else:
                    st.error("Please fill in name, area, and item.")

    st.divider()

    # Display restaurants
    st.subheader("All Restaurants")

    # Filter by day
    day_filter = st.selectbox(
        "Filter by availability",
        ["All", "Available Today", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    )

    filtered = restaurants.copy()

    if day_filter == "Available Today":
        today = datetime.now()
        day_name = get_day_name(today)
        if day_name:
            filtered = filtered[
                (filtered["specific_day"] == "") |
                (filtered["specific_day"].str.lower() == day_name.lower())
            ]
    elif day_filter != "All":
        filtered = filtered[
            (filtered["specific_day"] == "") |
            (filtered["specific_day"].str.lower() == day_filter.lower())
        ]

    # Display as cards
    for idx, row in filtered.iterrows():
        with st.container():
            cols = st.columns([3, 2, 2, 1, 1, 1])

            with cols[0]:
                st.write(f"**{row['name']}**")
            with cols[1]:
                st.write(row["area"])
            with cols[2]:
                st.write(row["item"])
            with cols[3]:
                st.write(f"{row['price']} SAR")
            with cols[4]:
                st.write(f"{row['travel_time']} min")
            with cols[5]:
                day = row["specific_day"]
                if day:
                    st.caption(day)
                else:
                    st.caption("Any")

            st.divider()


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()

    # Main tabs
    tabs = st.tabs(["🎯 Today's Pick", "📅 This Month", "📜 History", "🍕 Restaurants"])

    with tabs[0]:
        render_recommendation_tab()

    with tabs[1]:
        render_month_tab()

    with tabs[2]:
        render_history_tab()

    with tabs[3]:
        render_restaurants_tab()


if __name__ == "__main__":
    main()
