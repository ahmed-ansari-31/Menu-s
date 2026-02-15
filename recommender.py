"""Recommendation algorithm for Daily Menu."""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


# Saudi work week: Sunday (6) to Thursday (3)
WORK_DAYS = {6: "Sunday", 0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday"}
THURSDAY = 3


def get_day_name(date: datetime) -> str:
    """Get day name from date."""
    return WORK_DAYS.get(date.weekday(), "")


def is_work_day(date: datetime) -> bool:
    """Check if date is a Saudi work day."""
    return date.weekday() in WORK_DAYS


def is_thursday(date: datetime) -> bool:
    """Check if date is Thursday (special day with no budget limit)."""
    return date.weekday() == THURSDAY


def get_month_visits(history: dict, year: int = None, month: int = None) -> list:
    """Get visits for a specific month (defaults to current month)."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    return [
        v for v in history.get("visits", [])
        if v["date"].startswith(f"{year:04d}-{month:02d}")
    ]


def get_monthly_stats(history: dict) -> dict:
    """Calculate monthly spending statistics."""
    visits = get_month_visits(history)

    if not visits:
        return {
            "days_visited": 0,
            "total_spent": 0,
            "current_average": 0,
            "status": "green",
            "target_daily": 22.5,
        }

    days_visited = len(visits)
    total_spent = sum(v["price"] for v in visits)
    current_average = total_spent / days_visited if days_visited > 0 else 0

    # Determine status based on average
    if current_average < 20:
        status = "green"
    elif current_average <= 25:
        status = "yellow"
    else:
        status = "red"

    return {
        "days_visited": days_visited,
        "total_spent": total_spent,
        "current_average": round(current_average, 1),
        "status": status,
        "target_daily": 22.5,
    }


def get_recent_visits(history: dict, days: int = 7) -> list:
    """Get visits from the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return [v for v in history.get("visits", []) if v["date"] >= cutoff]


def get_recent_restaurant_names(history: dict, days: int = 7) -> set:
    """Get names of restaurants visited in the last N days."""
    recent = get_recent_visits(history, days)
    return {v["restaurant"] for v in recent}


def get_available_restaurants(restaurants: pd.DataFrame, date: datetime) -> pd.DataFrame:
    """Filter restaurants available on a specific day."""
    day_name = get_day_name(date)

    if not day_name:
        return pd.DataFrame()  # Not a work day

    # Available if: no specific day restriction OR matches today
    available = restaurants[
        (restaurants["specific_day"] == "") |
        (restaurants["specific_day"].str.lower() == day_name.lower())
    ]

    return available.copy()


def get_days_since_visit(restaurant_name: str, history: dict) -> int:
    """Get number of days since last visit to a restaurant."""
    visits = history.get("visits", [])
    restaurant_visits = [v for v in visits if v["restaurant"] == restaurant_name]

    if not restaurant_visits:
        return 999  # Never visited

    last_visit = max(v["date"] for v in restaurant_visits)
    last_date = datetime.strptime(last_visit, "%Y-%m-%d")
    return (datetime.now() - last_date).days


def calculate_scores(
    restaurants: pd.DataFrame,
    history: dict,
    date: datetime
) -> pd.DataFrame:
    """Calculate recommendation scores for each restaurant."""
    df = restaurants.copy()
    stats = get_monthly_stats(history)
    thursday = is_thursday(date)

    # Calculate recency score (0-1, higher = not visited recently)
    df["days_since_visit"] = df["name"].apply(lambda x: get_days_since_visit(x, history))
    df["recency_score"] = df["days_since_visit"].apply(lambda x: min(x, 30) / 30)

    # Calculate budget score (0-1)
    if thursday:
        # Thursday: budget doesn't matter for selection
        df["budget_score"] = 0.5
    else:
        current_avg = stats["current_average"]
        if current_avg > 25:
            # Over budget: prefer cheaper (lower price = higher score)
            df["budget_score"] = 1 - (df["price"] / 40)
        elif current_avg < 20:
            # Under budget: can afford pricier (higher price = higher score)
            df["budget_score"] = df["price"] / 40
        else:
            # On target: neutral
            df["budget_score"] = 0.5

    # Calculate final score
    if thursday:
        # Thursday: only recency matters
        df["final_score"] = df["recency_score"]
    else:
        # Normal days: balance recency and budget
        df["final_score"] = df["recency_score"] * 0.5 + df["budget_score"] * 0.5

    return df


def get_recommendation(
    restaurants: pd.DataFrame,
    history: dict,
    date: datetime = None
) -> Optional[dict]:
    """Get the top restaurant recommendation for today."""
    date = date or datetime.now()

    if not is_work_day(date):
        return None

    # Get available restaurants for today
    available = get_available_restaurants(restaurants, date)

    if available.empty:
        return None

    # Exclude restaurants visited in last 7 days
    recent_restaurants = get_recent_restaurant_names(history, days=7)
    available = available[~available["name"].isin(recent_restaurants)]

    if available.empty:
        # All restaurants visited recently, allow repeats
        available = get_available_restaurants(restaurants, date)

    # Calculate scores
    scored = calculate_scores(available, history, date)

    # Get top recommendation
    top = scored.sort_values("final_score", ascending=False).iloc[0]

    return {
        "name": top["name"],
        "area": top["area"],
        "item": top["item"],
        "price": top["price"],
        "travel_time": top["travel_time"],
        "days_since_visit": top["days_since_visit"],
        "recency_score": round(top["recency_score"], 2),
        "budget_score": round(top["budget_score"], 2),
        "final_score": round(top["final_score"], 2),
    }


def explain_recommendation(recommendation: dict, history: dict, date: datetime = None) -> str:
    """Generate human-readable explanation for the recommendation."""
    date = date or datetime.now()
    stats = get_monthly_stats(history)
    thursday = is_thursday(date)

    parts = []

    # Recency explanation
    days = recommendation["days_since_visit"]
    if days >= 999:
        parts.append("You've never been here before!")
    elif days > 14:
        parts.append(f"It's been {days} days since your last visit.")
    elif days > 7:
        parts.append(f"Last visited {days} days ago.")

    # Budget explanation (skip for Thursday)
    if not thursday:
        price = recommendation["price"]
        avg = stats["current_average"]

        if avg > 25:
            parts.append(f"At {price} SAR, this helps bring your monthly average down from {avg} SAR.")
        elif avg < 20 and price > 25:
            parts.append(f"Your average is low ({avg} SAR), so you can treat yourself today!")
        elif 20 <= avg <= 25:
            parts.append(f"Your monthly average ({avg} SAR) is on track.")
    else:
        parts.append("It's Thursday! Treat yourself - no budget restrictions today.")

    return " ".join(parts)


def get_all_recommendations(
    restaurants: pd.DataFrame,
    history: dict,
    date: datetime = None,
    limit: int = 5
) -> list:
    """Get top N restaurant recommendations."""
    date = date or datetime.now()

    if not is_work_day(date):
        return []

    available = get_available_restaurants(restaurants, date)

    if available.empty:
        return []

    # Exclude recently visited
    recent_restaurants = get_recent_restaurant_names(history, days=7)
    filtered = available[~available["name"].isin(recent_restaurants)]

    if filtered.empty:
        filtered = available

    scored = calculate_scores(filtered, history, date)
    top_n = scored.sort_values("final_score", ascending=False).head(limit)

    return [
        {
            "name": row["name"],
            "area": row["area"],
            "item": row["item"],
            "price": row["price"],
            "travel_time": row["travel_time"],
            "days_since_visit": row["days_since_visit"],
            "final_score": round(row["final_score"], 2),
        }
        for _, row in top_n.iterrows()
    ]
