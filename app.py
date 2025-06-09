import streamlit as st
import boto3
import pandas as pd
import os
from io import BytesIO
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import seaborn as sns

load_dotenv()

# Remove or comment out the following line if present:
# st.set_page_config(page_title="Repo Insights", layout="wide")

# Read BUCKET_NAME and FOLDER_PREFIX from environment variables
BUCKET_NAME = os.getenv("BUCKET_NAME")
FOLDER_PREFIX = os.getenv("FOLDER_PREFIX")
TABLES = {
    "commits": "commits.csv",
    "stars": "stars.csv",
    "forks": "forks.csv",
    "issues": "issues.csv",
    "pr": "pr.csv"
}

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION"),
    )

def read_csv_from_s3(filename):
    key = FOLDER_PREFIX + filename
    s3 = get_s3_client()
    response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_csv(BytesIO(response["Body"].read()))

@st.cache_data(show_spinner=True)
def load_all_tables():
    data = {}
    for name, fname in TABLES.items():
        try:
            df = read_csv_from_s3(fname)
            data[name] = df
        except Exception as e:
            st.warning(f"Could not load {fname}: {e}")
            data[name] = pd.DataFrame()
    return data

st.title("Agntcy Repo Insights")
data = load_all_tables()

# --- SUMMARY CARDS ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("⭐ Total Stars", len(data["stars"]))
col2.metric("🍴 Total Forks", len(data["forks"]))
col3.metric("⬆️ Total Commits", len(data["commits"]))
col4.metric("🐞 Total Issues", len(data["issues"]))
col5.metric("🔀 Total PRs", len(data["pr"]))

# --- WEEKLY CUMULATIVE GROWTH CHARTS (VERTICALLY STACKED) ---

def plot_weekly_cumulative(df, date_col, label, color, ax):
    if df.empty or date_col not in df.columns:
        ax.set_axis_off()
        ax.set_title(f"No data for {label}")
        return

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    
    # Calculate weekly and cumulative counts
    weekly_counts = df[date_col].dt.to_period("W").value_counts().sort_index()
    weekly_counts = weekly_counts.sort_index()
    cumulative = weekly_counts.cumsum()

    # Plot cumulative line
    ax.plot(cumulative.index.to_timestamp(), cumulative.values, label=f"Cumulative {label}", color=color, alpha=0.85, linewidth=2)

    # Create secondary y-axis for weekly bars (optional)
    ax2 = ax.twinx()
    ax2.bar(weekly_counts.index.to_timestamp(), weekly_counts.values, width=6, color=color, alpha=0.3, label=f"Weekly {label}")

    # Labeling and styling
    ax.set_title(f"Weekly & Cumulative {label}", fontsize=14)
    ax.set_xlabel("Week")
    ax.set_ylabel(f"Cumulative {label}", color=color)
    ax2.set_ylabel(f"Weekly {label}", color=color)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="center left", fontsize=9)
    ax2.legend(loc="center right", fontsize=9)
    ax.tick_params(labelrotation=30, labelsize=9)
    sns.despine(ax=ax)

st.header("Weekly Cumulative Growth")

# Stars
st.subheader("Stars")
fig, ax = plt.subplots(figsize=(10, 3))
plot_weekly_cumulative(data["stars"], "starred_at", "Stars", "gold", ax)
st.pyplot(fig, use_container_width=True)

# Forks
st.subheader("Forks")
fig, ax = plt.subplots(figsize=(10, 3))
plot_weekly_cumulative(data["forks"], "created_at", "Forks", "mediumorchid", ax)
st.pyplot(fig, use_container_width=True)

# Commits
st.subheader("Commits")
fig, ax = plt.subplots(figsize=(10, 3))
plot_weekly_cumulative(data["commits"], "date", "Commits", "deepskyblue", ax)
st.pyplot(fig, use_container_width=True)

# Issues
st.subheader("Issues")
fig, ax = plt.subplots(figsize=(10, 3))
plot_weekly_cumulative(data["issues"], "created_at", "Issues", "limegreen", ax)
st.pyplot(fig, use_container_width=True)

# PRs
st.subheader("PRs")
fig, ax = plt.subplots(figsize=(10, 3))
plot_weekly_cumulative(data["pr"], "created_at", "PRs", "tomato", ax)
st.pyplot(fig, use_container_width=True)

# --- TOP REPOSITORIES ---

st.header("Top Repositories")

repo_cols = st.columns(2)

# Top by Stars
st.subheader("By Stars")
df = data["stars"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts().head(10)
    fig, ax = plt.subplots(figsize=(7,4))
    sns.barplot(y=repo_counts.index, x=repo_counts.values, color="gold", ax=ax)
    ax.set_xlabel("# of Stars")
    ax.set_ylabel("Repository")
    ax.set_title("Top 10 by Stars", fontsize=12)
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)
    st.pyplot(fig, use_container_width=True)
else:
    st.info("No stars data.")

# Top by Commits
st.subheader("By Commits")
df = data["commits"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts().head(10)
    fig, ax = plt.subplots(figsize=(7,4))
    sns.barplot(y=repo_counts.index, x=repo_counts.values, color="deepskyblue", ax=ax)
    ax.set_xlabel("# of Commits")
    ax.set_ylabel("Repository")
    ax.set_title("Top 10 by Commits", fontsize=12)
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)
    st.pyplot(fig, use_container_width=True)
else:
    st.info("No commits data.")
