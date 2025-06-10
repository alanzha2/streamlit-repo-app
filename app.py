import streamlit as st
import boto3
import pandas as pd
import os
from io import BytesIO
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px

load_dotenv()

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

def plot_weekly_cumulative_plotly(df, date_col, label, color):
    if df.empty or date_col not in df.columns:
        return go.Figure().update_layout(title=f"No data for {label}")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    weekly = df[date_col].dt.to_period("W").value_counts().sort_index()
    weekly = weekly.sort_index()
    cumulative = weekly.cumsum()

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=weekly.index.to_timestamp(),
        y=weekly.values,
        name=f"Weekly {label}",
        marker_color=color,
        opacity=0.3,
        hovertemplate="%{y} new " + label + "<br>%{x|%b %d, %Y}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=cumulative.index.to_timestamp(),
        y=cumulative.values,
        name=f"Cumulative {label}",
        mode="lines+markers",
        line=dict(color=color, width=2),
        hovertemplate="%{y} total " + label + "<br>%{x|%b %d, %Y}<extra></extra>"
    ))

    fig.update_layout(
        title=f"Weekly and Cumulative {label}",
        xaxis_title="Week",
        yaxis_title=label,
        hovermode="x unified",
        template="simple_white",
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig

def filter_df(df, date_col):
    if df.empty or date_col not in df.columns:
        return df
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[date_col] = df[date_col].dt.tz_localize(None)  # ensure tz-naive
    df = df[(df[date_col] >= pd.to_datetime(date_range[0])) & (df[date_col] <= pd.to_datetime(date_range[1]))]
    if selected_repo != "All" and "repo_name" in df.columns:
        df = df[df["repo_name"] == selected_repo]
    return df

st.title("Agntcy Repo Insights")
data = load_all_tables()

st.sidebar.header("📊 Filters")
repo_options = sorted(set(
    r for df in data.values() if not df.empty and "repo_name" in df.columns for r in df["repo_name"].unique()
))
selected_repo = st.sidebar.selectbox("Filter by repository", ["All"] + repo_options)

min_date = pd.Timestamp("2100-01-01")
max_date = pd.Timestamp("1900-01-01")
for df in data.values():
    for col in ["created_at", "starred_at", "date"]:
        if col in df.columns:
            dates = pd.to_datetime(df[col], errors="coerce")
            dates = dates.dt.tz_localize(None)  # force tz-naive
            if not dates.empty:
                min_date = min(min_date, dates.min())
                max_date = max(max_date, dates.max())

date_range = st.sidebar.date_input("Filter by date range", (min_date, max_date))

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("⭐ Total Stars", len(data["stars"]))
col2.metric("🍴 Total Forks", len(data["forks"]))
col3.metric("⬆️ Total Commits", len(data["commits"]))
col4.metric("🐞 Total Issues", len(data["issues"]))
col5.metric("🔀 Total PRs", len(data["pr"]))

st.header("Weekly Cumulative Growth")

for label, key, date_col, color in [
    ("Stars", "stars", "starred_at", "gold"),
    ("Forks", "forks", "created_at", "mediumorchid"),
    ("Commits", "commits", "date", "deepskyblue"),
    ("Issues", "issues", "created_at", "limegreen"),
    ("PRs", "pr", "created_at", "tomato")
]:
    st.subheader(label)
    filtered = filter_df(data[key], date_col)
    fig = plot_weekly_cumulative_plotly(filtered, date_col, label, color)
    st.plotly_chart(fig, use_container_width=True)
    if not filtered.empty:
        st.download_button(
            f"Download {label} CSV",
            data=filtered.to_csv(index=False),
            file_name=f"{label.lower()}_filtered.csv",
            mime="text/csv"
        )

st.header("Top Repositories")

st.subheader("By Stars")
df = data["stars"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
    repo_counts.columns = ["repo_name", "stars"]
    fig = px.bar(repo_counts, x="stars", y="repo_name", orientation="h", color_discrete_sequence=["gold"], title="Top 10 by Stars")
    fig.update_layout(yaxis_title="Repository", xaxis_title="# of Stars", height=350)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No stars data.")

st.subheader("By Commits")
df = data["commits"]
if not df.empty and "repo_name" in df.columns:
    repo_counts = df["repo_name"].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
    repo_counts.columns = ["repo_name", "commits"]
    fig = px.bar(repo_counts, x="commits", y="repo_name", orientation="h", color_discrete_sequence=["deepskyblue"], title="Top 10 by Commits")
    fig.update_layout(yaxis_title="Repository", xaxis_title="# of Commits", height=350)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No commits data.")

# --- Top Contributors ---
st.header("Top Contributors")

col1, col2, col3 = st.columns(3)

# Commits
with col1:
    st.subheader("By Commits")
    df = data["commits"]
    if not df.empty and "author_login" in df.columns:
        top_committers = df["author_login"].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
        top_committers.columns = ["user", "commits"]
        fig = px.bar(top_committers, x="commits", y="user", orientation="h", color_discrete_sequence=["deepskyblue"], height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No commit data.")

# PRs
with col2:
    st.subheader("By PRs")
    df = data["pr"]
    if not df.empty and "user" in df.columns:
        top_prs = df["user"].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
        top_prs.columns = ["user", "prs"]
        fig = px.bar(top_prs, x="prs", y="user", orientation="h", color_discrete_sequence=["tomato"], height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No PR data.")

# Issues
with col3:
    st.subheader("By Issues")
    df = data["issues"]
    if not df.empty and "user" in df.columns:
        top_issues = df["user"].value_counts().nlargest(10).sort_values(ascending=True).reset_index()
        top_issues.columns = ["user", "issues"]
        fig = px.bar(top_issues, x="issues", y="user", orientation="h", color_discrete_sequence=["limegreen"], height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No issues data.")

# --- Top Contributors Table ---
commit_df = data["commits"][["author_login", "date"]].rename(columns={"author_login": "user", "date": "commit_date"})
issue_df = data["issues"]["user"]
pr_df = data["pr"]["user"]

commit_counts = commit_df["user"].value_counts()
issue_counts = issue_df.value_counts()
pr_counts = pr_df.value_counts()

top_committers = set(commit_counts.nlargest(10).index)
top_issuers = set(issue_counts.nlargest(10).index)
top_prs = set(pr_counts.nlargest(10).index)

all_top = top_committers.union(top_issuers).union(top_prs)

rows = []
for user in all_top:
    commits = commit_counts.get(user, 0)
    issues = issue_counts.get(user, 0)
    prs = pr_counts.get(user, 0)
    last_commit = pd.to_datetime(commit_df[commit_df["user"] == user]["commit_date"], errors="coerce").dt.tz_localize(None).max()
    last_issue = pd.to_datetime(data["issues"][data["issues"]["user"] == user]["created_at"], errors="coerce").dt.tz_localize(None).max()
    last_pr = pd.to_datetime(data["pr"][data["pr"]["user"] == user]["created_at"], errors="coerce").dt.tz_localize(None).max()
    valid_dates = [d for d in [last_commit, last_issue, last_pr] if pd.notnull(d)]
    last_contribution = max(valid_dates) if valid_dates else None
    rows.append({
        "User": user,
        "Commits": commits,
        "Issues": issues,
        "PRs": prs,
        "Last Contribution": last_contribution.date() if pd.notnull(last_contribution) else None
    })

contrib_df = pd.DataFrame(rows).sort_values(by=["Commits", "Issues", "PRs"], ascending=False)
st.subheader("Top Contributor Summary Table")
st.dataframe(contrib_df.reset_index(drop=True), use_container_width=True)