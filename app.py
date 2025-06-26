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
    "pr": "pr.csv",
    "downloads" : "downloads.csv",
    "discussions" : "discussions.csv"

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
        except Exception as e:
            st.warning(f"Could not load {fname}: {e}")
            df = pd.DataFrame()
        data[name] = df  # always assign
    return data

st.title("Agntcy Repo Insights")
data = load_all_tables()

downloads_df = data["downloads"]

# Ensure process_time is datetime
downloads_df["process_time"] = pd.to_datetime(downloads_df["process_time"])

# Get latest snapshot
latest_ts = downloads_df["process_time"].max()
latest_downloads = downloads_df[downloads_df["process_time"] == latest_ts]

# --- SUMMARY CARDS ---

# First row: 4 cards
top1, top2, top3, top4 = st.columns(4)
top1.metric("⭐\nStars", len(data["stars"]))
top2.metric("🍴\nForks", len(data["forks"]))
top3.metric("⬆️\nCommits", len(data["commits"]))
top4.metric("🐞\nIssues", len(data["issues"]))

# Second row: 4 cards
bot1, bot2, bot3, bot4 = st.columns(4)
bot1.metric("🔀\nPRs", len(data["pr"]))
bot2.metric("📥\nPkg Downloads", f"{int(latest_downloads['total_downloads'].sum()):,}")
bot3.metric("💬\nDiscussions", len(data["discussions"]))
bot4.metric("🔼\nUpvotes", f"{int(data['discussions']['upvote_count'].sum()):,}")

def plot_cumulative_by_period(df, date_col, label, color, ax, freq="W", show_bar=True):
    """
    Plot cumulative and period counts on dual y-axis with configurable frequency.

    freq: "D" (Daily), "W" (Weekly), "M" (Monthly), "Q" (Quarterly), "Y" (Yearly)
    show_bar: if True, show period-level bars on secondary y-axis
    """
    if df.empty or date_col not in df.columns:
        ax.set_axis_off()
        ax.set_title(f"No data for {label}")
        return

    # Friendly frequency label
    freq_labels = {
        "D": "Daily",
        "W": "Weekly",
        "M": "Monthly",
        "Q": "Quarterly",
        "Y": "Yearly"
    }
    freq_name = freq_labels.get(freq.upper(), freq.upper())

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    period_series = df[date_col].dt.to_period(freq)
    period_counts = period_series.value_counts().sort_index()
    cumulative = period_counts.cumsum()
    period_timestamps = cumulative.index.to_timestamp()

    # Plot cumulative line
    ax.plot(period_timestamps, cumulative.values, label=f"Cumulative {label}",
            color=color, alpha=0.85, linewidth=2)

    if show_bar:
        # Plot period counts on secondary axis
        ax2 = ax.twinx()
        bar_width = {"D": 0.7, "W": 6, "M": 20, "Q": 60, "Y": 90}.get(freq.upper(), 6)
        ax2.bar(period_timestamps, period_counts.values,
                width=bar_width, color=color, alpha=0.3, label=f"{freq_name} {label}")
        ax2.set_ylabel(f"{freq_name} {label}", color=color)
        ax2.legend(loc="center right", fontsize=9)
    else:
        ax2 = None

    # Styling
    ax.set_title(f"{freq_name} & Cumulative {label}", fontsize=14)
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Cumulative {label}", color=color)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="center left", fontsize=9)
    ax.tick_params(labelrotation=30, labelsize=9)
    sns.despine(ax=ax)


st.header("Weekly Cumulative Growth")

# Stars
st.subheader("Stars")
fig, ax = plt.subplots(figsize=(10, 3))
plot_cumulative_by_period(data["stars"], date_col="starred_at", label="Stars", color="gold", ax=ax, freq="W")
st.pyplot(fig, use_container_width=True)

# Forks
st.subheader("Forks")
fig, ax = plt.subplots(figsize=(10, 3))
plot_cumulative_by_period(data["forks"], date_col="created_at", label="Forks", color="mediumorchid", ax=ax, freq="W")
st.pyplot(fig, use_container_width=True)

# Commits
st.subheader("Commits")
fig, ax = plt.subplots(figsize=(10, 3))
plot_cumulative_by_period(data["commits"], date_col="date", label="Commits", color="deepskyblue", ax=ax, freq="W")
st.pyplot(fig, use_container_width=True)

# Issues
st.subheader("Issues")
fig, ax = plt.subplots(figsize=(10, 3))
plot_cumulative_by_period(data["issues"], date_col="created_at", label="Issues", color="limegreen", ax=ax, freq="W")
st.pyplot(fig, use_container_width=True)

# PRs
st.subheader("PRs")
fig, ax = plt.subplots(figsize=(10, 3))
plot_cumulative_by_period(data["pr"], date_col="created_at", label="PRs", color="tomato", ax=ax, freq="W")
st.pyplot(fig, use_container_width=True)

# --- DOWNLOAD TRENDS OVER TIME ---
st.subheader("📈 Download Trends (Snapshot Per Day)")
df = data["downloads"]

if not df.empty and "process_time" in df.columns and "total_downloads" in df.columns:
    df["process_time"] = pd.to_datetime(df["process_time"])
    df["date"] = df["process_time"].dt.date

    # Get the latest process_time per day
    latest_per_day = (
        df.sort_values("process_time")
          .groupby(["date", "name"], as_index=False)
          .last()  # latest snapshot for each package on each day
    )

    # Sum downloads across all packages for each day
    daily_totals = (
        latest_per_day.groupby("date")["total_downloads"]
        .sum()
        .reset_index()
        .sort_values("date")
    )

    # Plot
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=daily_totals, x="date", y="total_downloads", color="#627D98", ax=ax)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Total Pkg Downloads")
    ax.set_title("Total Pkg Downloads (Snapshot Per Day)", fontsize=14)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

    # Add value labels
    for i, row in daily_totals.iterrows():
        ax.text(i, row["total_downloads"] + 5, f"{int(row['total_downloads']):,}", 
                ha="center", va="bottom", fontsize=8)

    st.pyplot(fig, use_container_width=True)

else:
    st.info("No downloads trend data available.")

# --- TOP REPOSITORIES ---

st.header("Top Repositories")

repo_cols = st.columns(2)

# Top by Stars
st.subheader("By Stars")
df = data["stars"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts()
    fig, ax = plt.subplots(figsize=(7,5))
    sns.barplot(y=repo_counts.index, x=repo_counts.values, color="gold", ax=ax)
    ax.set_xlabel("# of Stars")
    ax.set_ylabel("Repository")
    ax.set_title("Top Repos by Stars", fontsize=12)
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)
    st.pyplot(fig, use_container_width=True)
else:
    st.info("No stars data.")

# Top by Commits
st.subheader("By Commits")
df = data["commits"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts()
    fig, ax = plt.subplots(figsize=(7,5))
    sns.barplot(y=repo_counts.index, x=repo_counts.values, color="deepskyblue", ax=ax)
    ax.set_xlabel("# of Commits")
    ax.set_ylabel("Repository")
    ax.set_title("Top Repos by Commits", fontsize=12)
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)
    st.pyplot(fig, use_container_width=True)
else:
    st.info("No commits data.")

# --- DOWNLOADS BY PACKAGE ---
st.header("📦 Downloads by Package")

df = latest_downloads.copy()
if not df.empty and "name" in df.columns and "total_downloads" in df.columns:
    df_sorted = df.sort_values("total_downloads", ascending=False)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=df_sorted,
        y="name", x="total_downloads",
        palette="Blues_d", ax=ax
    )
    ax.set_xlabel("Total Downloads")
    ax.set_ylabel("Package Name")
    ax.set_title("Total Downloads by Package", fontsize=14)
    ax.grid(True, axis="x", linestyle="--", alpha=0.4)

    # Add download count labels to the ends of the bars
    for i, v in enumerate(df_sorted["total_downloads"]):
        ax.text(v + 5, i, f"{v:,}", color="black", va="center", fontsize=9)

    st.pyplot(fig, use_container_width=True)
else:
    st.info("No downloads data available.")
