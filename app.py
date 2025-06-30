import streamlit as st
import boto3
import pandas as pd
import os
from io import BytesIO
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go

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


repo_name_columns = [df["repo_name"] for df in data.values() if "repo_name" in df.columns]
all_repo_names = pd.Series(pd.concat(repo_name_columns).dropna().unique()).sort_values().tolist()

with st.sidebar.expander("📂 Filter by Repo", expanded=False):
    # "Select all" checkbox
    select_all = st.checkbox("Select all repositories", value=True)

    # If "select all" is checked, set default to all_repo_names
    if select_all:
        selected_repos = st.multiselect(
            "Select repositories to include:",
            options=all_repo_names,
            default=all_repo_names,
            key="repo_selector"
        )
    else:
        selected_repos = st.multiselect(
            "Select repositories to include:",
            options=all_repo_names,
            key="repo_selector"
        )

# Apply filtering to each relevant dataset
for name, df in data.items():
    if "repo_name" in df.columns:
        data[name] = df[df["repo_name"].isin(selected_repos)]

downloads_df = data["downloads"]
downloads_df["process_time"] = pd.to_datetime(downloads_df["process_time"])
latest_ts = downloads_df["process_time"].max()
latest_downloads = downloads_df[downloads_df["process_time"] == latest_ts]


# --- SUMMARY CARDS ---
top1, top2, top3, top4 = st.columns(4)
top1.metric("\U0001F4E5\nPkg Downloads", f"{int(latest_downloads['total_downloads'].sum()):,}")
top2.metric("\U0001F374\nForks", len(data["forks"]))
top3.metric("\u2B06\ufe0f\nCommits", len(data["commits"]))
top4.metric("\U0001F41E\nIssues", len(data["issues"]))

bot1, bot2, bot3, bot4 = st.columns(4)
bot1.metric("\U0001F500\nPRs", len(data["pr"]))
bot2.metric("\u2B50\nStars", len(data["stars"]))
bot3.metric("\U0001F4AC\nDiscussions", len(data["discussions"]))
bot4.metric("\U0001F53C\nUpvotes", f"{int(data['discussions']['upvote_count'].sum()):,}")

st.header("Weekly Cumulative Growth")

# --- DOWNLOAD TRENDS OVER TIME ---
st.subheader("\U0001F4C8 Download Trends (Snapshot Per Day)")
df = downloads_df.copy()
if not df.empty and "process_time" in df.columns and "total_downloads" in df.columns:
    df["date"] = df["process_time"].dt.date
    latest_per_day = df.sort_values("process_time").groupby(["date", "name"], as_index=False).last()
    daily_totals = latest_per_day.groupby("date")["total_downloads"].sum().reset_index().sort_values("date")
    fig = px.line(
        daily_totals,
        x="date",
        y="total_downloads",
        markers=True,
        text="total_downloads",  # Show value as label
        labels={"date": "Date", "total_downloads": "Cumulative Total Pkg Downloads"},
        title="Total Pkg Downloads (Snapshot Per Day)"
    )
    fig.update_traces(textposition="top center")  # Position the label above the marker
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No downloads trend data available.")

# --- DOWNLOADS BY PACKAGE ---
st.header("\U0001F4E6 Downloads by Package")
df = latest_downloads.copy()
if not df.empty and "name" in df.columns and "total_downloads" in df.columns:
    df_sorted = df.sort_values("total_downloads", ascending=False)
    fig = px.bar(
        df_sorted,
        x="total_downloads",
        y="name",
        orientation="h",
        labels={"total_downloads": "Total Downloads", "name": "Package"},
        title="Total Downloads by Package",
        text="total_downloads"
    )
    fig.update_traces(textfont_size=14, textposition="outside")
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_title="Total Downloads",
        yaxis_title="Package Name",
        font=dict(size=14),
        bargap=0.3,
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No downloads data available.")


# --- GENERIC TIME SERIES CHARTS ---
def plot_time_series(df, date_col, label, color, freq="W"):
    if df.empty or date_col not in df.columns:
        st.info(f"No {label} data available.")
        return

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["period"] = df[date_col].dt.to_period(freq).dt.to_timestamp()
    grouped = df.groupby("period").size().reset_index(name="count")
    grouped["cumulative"] = grouped["count"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=grouped["period"], y=grouped["count"],
                         name=f"{label} per {freq}", marker_color=color, opacity=0.5))
    fig.add_trace(go.Scatter(x=grouped["period"], y=grouped["cumulative"],
                             mode="lines+markers", name=f"Cumulative {label}", line=dict(color=color)))
    fig.update_layout(title=f"{label} ({freq}) with Cumulative Total",
                      xaxis_title="Date", yaxis_title=label, legend_title=label)
    st.plotly_chart(fig, use_container_width=True)


# --- TIME SERIES CHARTS ---
st.subheader("Stars")
plot_time_series(data["stars"], date_col="starred_at", label="Stars", color="gold")

st.subheader("Forks")
plot_time_series(data["forks"], date_col="created_at", label="Forks", color="mediumpurple")

st.subheader("Commits")
plot_time_series(data["commits"], date_col="date", label="Commits", color="deepskyblue")

st.subheader("Issues")
plot_time_series(data["issues"], date_col="created_at", label="Issues", color="limegreen")

st.subheader("PRs")
plot_time_series(data["pr"], date_col="created_at", label="PRs", color="tomato")



# --- TOP REPOSITORIES ---
st.header("Top Repositories")

st.subheader("By Stars")
df = data["stars"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts().reset_index()
    repo_counts.columns = ["repo", "count"]
    repo_counts = repo_counts.sort_values("count", ascending=True)
    fig = px.bar(repo_counts, x="count", y="repo", orientation="h", color_discrete_sequence=["gold"],
                 title="Top Repos by Stars", text="count")
    fig.update_traces(textfont_size=14,textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No stars data.")

st.subheader("By Commits")
df = data["commits"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts().reset_index()
    repo_counts.columns = ["repo", "count"]
    repo_counts = repo_counts.sort_values("count", ascending=True)
    fig = px.bar(repo_counts, x="count", y="repo", orientation="h", color_discrete_sequence=["deepskyblue"],
                 title="Top Repos by Commits", text="count")
    fig.update_traces(textfont_size=14,textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No commits data.")






