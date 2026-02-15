"""Database operations for Daily Menu - GitHub JSON storage."""

import json
import base64
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


HISTORY_FILE = "visit_history.json"
LOCAL_HISTORY_PATH = Path(__file__).parent / HISTORY_FILE


def load_restaurants() -> pd.DataFrame:
    """Load restaurant data from data.tsv."""
    data_path = Path(__file__).parent / "data.tsv"
    df = pd.read_csv(data_path, sep="\t")
    df.columns = ["name", "area", "specific_day", "item", "travel_time", "price"]
    df["specific_day"] = df["specific_day"].fillna("")
    df["travel_time"] = pd.to_numeric(df["travel_time"], errors="coerce").fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(int)
    return df


def _get_github_config():
    """Get GitHub configuration from environment variables or Streamlit secrets."""
    # Try environment variables first (for Docker)
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")

    if token and repo and not token.startswith("ghp_your"):
        return {"token": token, "repo": repo}

    # Fall back to Streamlit secrets
    try:
        return {
            "token": st.secrets["github"]["token"],
            "repo": st.secrets["github"]["repo"],
        }
    except (KeyError, FileNotFoundError, AttributeError):
        return None


def _github_request(method: str, endpoint: str, **kwargs):
    """Make authenticated request to GitHub API."""
    config = _get_github_config()
    if not config:
        return None

    headers = {
        "Authorization": f"token {config['token']}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{config['repo']}/contents/{endpoint}"
    response = requests.request(method, url, headers=headers, **kwargs)
    return response


def load_history() -> dict:
    """Load visit history from GitHub or local file."""
    # Try GitHub first
    response = _github_request("GET", HISTORY_FILE)

    if response and response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content)

    # Fall back to local file
    if LOCAL_HISTORY_PATH.exists():
        with open(LOCAL_HISTORY_PATH, "r") as f:
            return json.load(f)

    # Return empty history if nothing exists
    return {"visits": []}


def save_history(history: dict) -> bool:
    """Save visit history to GitHub and local file."""
    content = json.dumps(history, indent=2)

    # Always save locally first
    with open(LOCAL_HISTORY_PATH, "w") as f:
        f.write(content)

    # Try to save to GitHub
    config = _get_github_config()
    if not config:
        return True  # Local save succeeded

    # Get current file SHA if it exists
    response = _github_request("GET", HISTORY_FILE)
    sha = None
    if response and response.status_code == 200:
        sha = response.json().get("sha")

    # Push to GitHub
    payload = {
        "message": f"Update visit history - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": base64.b64encode(content.encode()).decode(),
    }
    if sha:
        payload["sha"] = sha

    response = _github_request("PUT", HISTORY_FILE, json=payload)
    return response and response.status_code in [200, 201]


def add_visit(restaurant: str, price: float, item: str, date: str = None) -> bool:
    """Add a new visit to history."""
    history = load_history()

    visit = {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "restaurant": restaurant,
        "price": price,
        "item": item,
    }

    history["visits"].append(visit)
    return save_history(history)


def delete_visit(date: str, restaurant: str) -> bool:
    """Delete a visit from history."""
    history = load_history()

    history["visits"] = [
        v for v in history["visits"]
        if not (v["date"] == date and v["restaurant"] == restaurant)
    ]

    return save_history(history)


def update_restaurant_data(df: pd.DataFrame) -> bool:
    """Save updated restaurant data to data.tsv."""
    data_path = Path(__file__).parent / "data.tsv"
    df_out = df.copy()
    df_out.columns = ["Restaurant name", "Area", "Specific day", "Item name", "Time to leave office", "estimate-Price"]
    df_out.to_csv(data_path, sep="\t", index=False)
    return True
