#!/usr/bin/env python3
"""
Agency-in-a-Box — Visual Dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A Streamlit dashboard that visualises the complete lead-to-revenue pipeline.

Usage:
    streamlit run dashboard.py

Requires:
    - Postgres running  (docker compose -f docker-compose.dev.yml up -d)
    - Demo data loaded  (python demo.py)
"""
from __future__ import annotations

import os
import textwrap

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import psycopg2.extras
import streamlit as st

# ── Config ───────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:localdev@localhost:5432/agency"
)

# Status colours used consistently throughout the dashboard
STATUS_COLOURS = {
    "new": "#6C757D",
    "approved": "#198754",
    "contacted": "#0D6EFD",
    "replied": "#6F42C1",
    "qualified": "#FFC107",
    "rejected": "#DC3545",
    "won": "#20C997",
    "lost": "#ADB5BD",
}

JOB_STATUS_COLOURS = {
    "pending": "#FFC107",
    "running": "#0D6EFD",
    "done": "#198754",
    "failed": "#DC3545",
    "dlq": "#6C757D",
}

# ── Database helpers ─────────────────────────────────────────────────────────


@st.cache_resource
def get_connection():
    """Persistent database connection (cached across re-runs)."""
    return psycopg2.connect(DATABASE_URL)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a read query and return a DataFrame."""
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        # Reconnect on stale connection
        conn.reset()
        return pd.read_sql_query(sql, conn, params=params)


# ── Page setup ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Agency-in-a-Box",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for cleaner look
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="stMetricValue"] { font-size: 2rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        border-radius: 6px 6px 0 0;
    }
    div[data-testid="stExpander"] details summary p { font-size: 1.05rem; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/robot-2.png",
        width=64,
    )
    st.title("Agency-in-a-Box")
    st.caption("Autonomous AI Dev Agency")
    st.divider()

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # Quick stats
    total_leads = query("SELECT count(*) AS n FROM leads").iloc[0]["n"]
    total_jobs = query("SELECT count(*) AS n FROM jobs").iloc[0]["n"]
    total_projects = query("SELECT count(*) AS n FROM projects").iloc[0]["n"]

    st.metric("Total Leads", int(total_leads))
    st.metric("Total Projects", int(total_projects))
    st.metric("Total Jobs", int(total_jobs))

    st.divider()
    st.markdown(
        "**Pipeline stages:**\n"
        "1. 🔍 Discovery\n"
        "2. 🏛️ KvK Validation\n"
        "3. 🎯 ICP Scoring\n"
        "4. 📱 Gate 1 (Telegram)\n"
        "5. 📧 Outreach\n"
        "6. 💬 Inbound Reply\n"
        "7. 🤖 SDR Draft\n"
        "8. ✅ Gate 2 (Approval)\n"
        "9. 🏗️ Project + GSD Job"
    )

# ── Header ───────────────────────────────────────────────────────────────────

st.title("🏭 Agency-in-a-Box — Pipeline Dashboard")
st.caption("Real-time view of the full lead → project → delivery pipeline")

# ── KPI Row ──────────────────────────────────────────────────────────────────

leads_df = query(
    """SELECT id, company_name, website, contact_email, contact_name,
              icp_score, icp_reasoning, status, kvk_validated,
              city, category, created_at, last_contact_date
       FROM leads ORDER BY created_at DESC"""
)
jobs_df = query(
    """SELECT j.id, j.job_type, j.status, j.retry_count, j.max_retries,
              j.created_at, j.updated_at,
              p.deliverable
       FROM jobs j
       LEFT JOIN projects p ON j.project_id = p.id
       ORDER BY j.created_at DESC"""
)
projects_df = query(
    """SELECT p.id, p.deliverable, p.tech_stack, p.status,
              p.github_repo, p.github_pr_url,
              l.company_name, b.current_spend, b.project_cap,
              p.created_at
       FROM projects p
       LEFT JOIN leads l ON p.lead_id = l.id
       LEFT JOIN project_budgets b ON p.budget_id = b.project_id
       ORDER BY p.created_at DESC"""
)
replies_df = query(
    """SELECT r.id, r.direction, r.status, r.body,
              r.sent_at, r.approved_by,
              l.company_name, l.contact_name
       FROM reply_threads r
       LEFT JOIN leads l ON r.lead_id = l.id
       ORDER BY r.sent_at DESC"""
)
outreach_df = query(
    """SELECT o.campaign_id, o.status, o.added_at,
              l.company_name, l.contact_email
       FROM outreach_campaigns o
       LEFT JOIN leads l ON o.lead_id = l.id
       ORDER BY o.added_at DESC"""
)

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

approved_count = int((leads_df["status"].isin(["approved", "contacted", "replied", "qualified", "won"])).sum())
rejected_count = int((leads_df["status"] == "rejected").sum())
avg_score = leads_df["icp_score"].mean() if not leads_df["icp_score"].isna().all() else 0
kvk_rate = leads_df["kvk_validated"].mean() * 100 if len(leads_df) else 0

kpi1.metric("📊 Total Leads", len(leads_df))
kpi2.metric("✅ Approved", approved_count)
kpi3.metric("❌ Rejected", rejected_count)
kpi4.metric("🎯 Avg ICP Score", f"{avg_score:.0f}")
kpi5.metric("🏛️ KvK Rate", f"{kvk_rate:.0f}%")
kpi6.metric("📧 Campaigns", len(outreach_df))

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_funnel, tab_leads, tab_scoring, tab_outreach, tab_replies, tab_projects, tab_jobs = st.tabs(
    ["🔄 Pipeline Funnel", "👥 Leads", "🎯 Scoring", "📧 Outreach", "💬 Replies", "🏗️ Projects", "⚙️ Jobs"]
)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 1 — Pipeline Funnel
# ─────────────────────────────────────────────────────────────────────────────
with tab_funnel:
    st.subheader("Lead-to-Revenue Funnel")

    # Calculate funnel stages from actual data
    total = len(leads_df)
    kvk_valid = int(leads_df["kvk_validated"].sum())
    scored = int(leads_df["icp_score"].notna().sum())
    contacted_plus = int(leads_df["status"].isin(["contacted", "replied", "qualified", "won"]).sum())
    replied = int(leads_df["status"].isin(["replied", "qualified", "won"]).sum())
    qualified = int(leads_df["status"].isin(["qualified", "won"]).sum())
    projects_count = len(projects_df)

    funnel_stages = ["Discovered", "KvK Validated", "ICP Scored", "Approved & Contacted", "Replied", "Qualified", "Project Created"]
    funnel_values = [total, kvk_valid, scored, contacted_plus, replied, qualified, projects_count]
    funnel_colours = ["#4ECDC4", "#45B7D1", "#5B8DEE", "#9B59B6", "#F39C12", "#E74C3C", "#2ECC71"]

    fig_funnel = go.Figure(
        go.Funnel(
            y=funnel_stages,
            x=funnel_values,
            textinfo="value+percent initial",
            marker=dict(color=funnel_colours),
            connector=dict(line=dict(color="#DDD", width=2)),
        )
    )
    fig_funnel.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(size=14),
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

    # Pipeline flow diagram
    st.subheader("Pipeline Architecture")
    flow_col1, flow_col2, flow_col3 = st.columns(3)

    with flow_col1:
        st.markdown(
            """
            #### 🔍 Discovery Phase
            ```
            Google Maps Scraping
                    ↓
            Apollo/AnyMail Enrichment
                    ↓
            GDPR Domain Hashing
                    ↓
            PostgreSQL (leads table)
            ```
            """
        )

    with flow_col2:
        st.markdown(
            """
            #### 🎯 Qualification Phase
            ```
            KvK Validation (NL)
                    ↓
            Gemini ICP Scoring
                    ↓
            Telegram Gate 1 (approve/reject)
                    ↓
            Instantly.ai Outreach
            ```
            """
        )

    with flow_col3:
        st.markdown(
            """
            #### 🏗️ Delivery Phase
            ```
            Inbound Reply → SDR Draft
                    ↓
            Telegram Gate 2 (approve reply)
                    ↓
            Project + Budget → GSD Job
                    ↓
            Code → Sandbox → Critic → PR
            ```
            """
        )

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 2 — Leads Table + Map
# ─────────────────────────────────────────────────────────────────────────────
with tab_leads:
    st.subheader("All Leads")

    # Filters
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        status_filter = st.multiselect(
            "Status",
            options=sorted(leads_df["status"].unique()),
            default=sorted(leads_df["status"].unique()),
        )
    with filter_col2:
        score_range = st.slider(
            "ICP Score Range",
            min_value=0,
            max_value=100,
            value=(0, 100),
        )
    with filter_col3:
        kvk_filter = st.selectbox("KvK Validated", ["All", "Yes", "No"])

    # Apply filters
    filtered = leads_df[leads_df["status"].isin(status_filter)]
    filtered = filtered[
        (filtered["icp_score"].fillna(0) >= score_range[0])
        & (filtered["icp_score"].fillna(0) <= score_range[1])
    ]
    if kvk_filter == "Yes":
        filtered = filtered[filtered["kvk_validated"] == True]
    elif kvk_filter == "No":
        filtered = filtered[filtered["kvk_validated"] == False]

    # Status breakdown side by side
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        status_counts = filtered["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        colour_map = {s: STATUS_COLOURS.get(s, "#999") for s in status_counts["status"]}
        fig_status = px.pie(
            status_counts,
            names="status",
            values="count",
            color="status",
            color_discrete_map=colour_map,
            title="Lead Status Distribution",
            hole=0.4,
        )
        fig_status.update_traces(textinfo="label+value+percent")
        fig_status.update_layout(height=350, margin=dict(t=40, b=10))
        st.plotly_chart(fig_status, use_container_width=True)

    with chart_col2:
        if filtered["city"].notna().any():
            city_counts = filtered["city"].dropna().value_counts().reset_index()
            city_counts.columns = ["city", "count"]
            fig_city = px.bar(
                city_counts,
                x="city",
                y="count",
                color="count",
                color_continuous_scale="Teal",
                title="Leads by City",
            )
            fig_city.update_layout(
                height=350,
                margin=dict(t=40, b=10),
                showlegend=False,
                xaxis_title="",
                yaxis_title="Leads",
            )
            st.plotly_chart(fig_city, use_container_width=True)
        else:
            st.info("No city data available.")

    # Data table
    display_cols = [
        "company_name", "city", "category", "contact_name",
        "contact_email", "icp_score", "status", "kvk_validated",
    ]
    st.dataframe(
        filtered[display_cols].rename(
            columns={
                "company_name": "Company",
                "city": "City",
                "category": "Category",
                "contact_name": "Contact",
                "contact_email": "Email",
                "icp_score": "ICP Score",
                "status": "Status",
                "kvk_validated": "KvK ✓",
            }
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "ICP Score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d"
            ),
            "KvK ✓": st.column_config.CheckboxColumn(),
            "Status": st.column_config.TextColumn(),
        },
    )

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 3 — ICP Scoring
# ─────────────────────────────────────────────────────────────────────────────
with tab_scoring:
    st.subheader("ICP Score Analysis")

    scored_df = leads_df[leads_df["icp_score"].notna()].copy()

    if len(scored_df) == 0:
        st.info("No scored leads yet. Run the demo first: `python demo.py`")
    else:
        score_col1, score_col2 = st.columns(2)

        with score_col1:
            # Horizontal bar chart sorted by score
            scored_sorted = scored_df.sort_values("icp_score", ascending=True)
            fig_scores = go.Figure()
            fig_scores.add_trace(
                go.Bar(
                    y=scored_sorted["company_name"],
                    x=scored_sorted["icp_score"],
                    orientation="h",
                    marker=dict(
                        color=scored_sorted["icp_score"],
                        colorscale=[
                            [0, "#DC3545"],
                            [0.4, "#FFC107"],
                            [0.6, "#198754"],
                            [1, "#0D6EFD"],
                        ],
                        showscale=True,
                        colorbar=dict(title="Score"),
                    ),
                    text=scored_sorted["icp_score"],
                    textposition="outside",
                )
            )
            fig_scores.add_vline(
                x=60,
                line_dash="dash",
                line_color="#DC3545",
                annotation_text="Threshold (60)",
            )
            fig_scores.update_layout(
                title="ICP Scores by Company",
                height=400,
                margin=dict(l=10, r=40, t=40, b=10),
                xaxis=dict(title="ICP Score", range=[0, 110]),
                yaxis=dict(title=""),
            )
            st.plotly_chart(fig_scores, use_container_width=True)

        with score_col2:
            # Score distribution histogram
            fig_hist = px.histogram(
                scored_df,
                x="icp_score",
                nbins=10,
                color_discrete_sequence=["#5B8DEE"],
                title="Score Distribution",
            )
            fig_hist.add_vline(
                x=60,
                line_dash="dash",
                line_color="#DC3545",
                annotation_text="Threshold",
            )
            fig_hist.update_layout(
                height=400,
                margin=dict(t=40, b=10),
                xaxis_title="ICP Score",
                yaxis_title="Count",
                bargap=0.1,
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        # Category breakdown
        if scored_df["category"].notna().any():
            fig_cat = px.box(
                scored_df[scored_df["category"].notna()],
                x="category",
                y="icp_score",
                color="category",
                title="ICP Score by Industry Category",
                points="all",
            )
            fig_cat.update_layout(
                height=350,
                margin=dict(t=40, b=10),
                showlegend=False,
                xaxis_title="",
                yaxis_title="ICP Score",
            )
            st.plotly_chart(fig_cat, use_container_width=True)

        # Reasoning table
        st.markdown("#### 📋 Scoring Reasoning")
        for _, row in scored_df.sort_values("icp_score", ascending=False).iterrows():
            score = int(row["icp_score"])
            icon = "🟢" if score >= 60 else "🔴"
            with st.expander(f"{icon} {row['company_name']} — Score: {score}/100"):
                st.markdown(f"**Category:** {row['category']}  |  **City:** {row['city']}")
                st.markdown(f"**Reasoning:** {row['icp_reasoning']}")

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 4 — Outreach
# ─────────────────────────────────────────────────────────────────────────────
with tab_outreach:
    st.subheader("Email Outreach Campaigns")

    if len(outreach_df) == 0:
        st.info("No outreach campaigns yet.")
    else:
        out_col1, out_col2 = st.columns([2, 1])

        with out_col1:
            st.dataframe(
                outreach_df.rename(
                    columns={
                        "campaign_id": "Campaign",
                        "company_name": "Company",
                        "contact_email": "Email",
                        "status": "Status",
                        "added_at": "Added",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        with out_col2:
            out_status = outreach_df["status"].value_counts().reset_index()
            out_status.columns = ["status", "count"]
            fig_out = px.pie(
                out_status,
                names="status",
                values="count",
                title="Campaign Status",
                color_discrete_sequence=px.colors.qualitative.Set2,
                hole=0.4,
            )
            fig_out.update_layout(height=300, margin=dict(t=40, b=10))
            st.plotly_chart(fig_out, use_container_width=True)

        # Campaign timeline
        outreach_df["added_at"] = pd.to_datetime(outreach_df["added_at"])
        fig_timeline = px.scatter(
            outreach_df,
            x="added_at",
            y="company_name",
            color="status",
            size_max=15,
            title="Outreach Timeline",
            labels={"added_at": "Date", "company_name": "Company"},
        )
        fig_timeline.update_traces(marker=dict(size=14, symbol="diamond"))
        fig_timeline.update_layout(height=350, margin=dict(t=40, b=10), yaxis_title="")
        st.plotly_chart(fig_timeline, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 5 — Reply Threads
# ─────────────────────────────────────────────────────────────────────────────
with tab_replies:
    st.subheader("Reply Threads (SDR Conversations)")

    if len(replies_df) == 0:
        st.info("No reply threads yet.")
    else:
        # Stats row
        r_col1, r_col2, r_col3 = st.columns(3)
        r_col1.metric("📥 Inbound", int((replies_df["direction"] == "inbound").sum()))
        r_col2.metric("📤 Outbound", int((replies_df["direction"] == "outbound").sum()))
        r_col3.metric("✅ Approved", int(replies_df["approved_by"].notna().sum()))

        st.divider()

        # Conversation view — group by company
        for company in replies_df["company_name"].unique():
            company_replies = replies_df[replies_df["company_name"] == company].sort_values("sent_at")
            with st.expander(f"💬 {company} ({len(company_replies)} messages)", expanded=True):
                for _, msg in company_replies.iterrows():
                    if msg["direction"] == "inbound":
                        st.markdown(
                            f"""<div style="background:#1a1a2e; border-left:4px solid #4ECDC4;
                            padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:8px;">
                            <strong>📥 {msg['contact_name'] or 'Prospect'}</strong>
                            <span style="color:#888; font-size:0.85em;"> · {msg['status']}</span>
                            <br/><span style="white-space:pre-wrap; color:#CCC;">{msg['body']}</span>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                    else:
                        approved = f" · ✅ Approved by {msg['approved_by']}" if msg["approved_by"] else ""
                        st.markdown(
                            f"""<div style="background:#162447; border-left:4px solid #5B8DEE;
                            padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:8px;">
                            <strong>🤖 AI SDR</strong>
                            <span style="color:#888; font-size:0.85em;"> · {msg['status']}{approved}</span>
                            <br/><span style="white-space:pre-wrap; color:#CCC;">{msg['body']}</span>
                            </div>""",
                            unsafe_allow_html=True,
                        )

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 6 — Projects
# ─────────────────────────────────────────────────────────────────────────────
with tab_projects:
    st.subheader("Active Projects")

    if len(projects_df) == 0:
        st.info("No projects yet. Qualify a lead to create a project.")
    else:
        for _, proj in projects_df.iterrows():
            spent = float(proj["current_spend"]) if pd.notna(proj["current_spend"]) else 0
            cap = float(proj["project_cap"]) if pd.notna(proj["project_cap"]) else 50
            pct = min(spent / cap, 1.0) if cap > 0 else 0
            tech = proj["tech_stack"] if isinstance(proj["tech_stack"], dict) else {}

            status_icon = {"planning": "📋", "in_progress": "🔨", "review": "🔍", "done": "✅"}.get(
                proj["status"], "❓"
            )

            st.markdown(f"### {status_icon} {proj['deliverable']}")

            p_col1, p_col2, p_col3 = st.columns([2, 1, 1])
            with p_col1:
                st.markdown(f"**Client:** {proj['company_name']}")
                st.markdown(f"**Status:** `{proj['status']}`")
                if proj["github_pr_url"]:
                    st.markdown(f"**PR:** [{proj['github_pr_url']}]({proj['github_pr_url']})")

            with p_col2:
                if tech:
                    st.markdown("**Tech Stack:**")
                    for k, v in tech.items():
                        st.markdown(f"- `{v}` ({k})")

            with p_col3:
                st.markdown("**Budget:**")
                st.progress(pct, text=f"${spent:.2f} / ${cap:.2f}")

                # Budget gauge
                fig_gauge = go.Figure(
                    go.Indicator(
                        mode="gauge+number+delta",
                        value=spent,
                        number=dict(prefix="$"),
                        delta=dict(reference=cap, decreasing=dict(color="#198754")),
                        gauge=dict(
                            axis=dict(range=[0, cap]),
                            bar=dict(color="#5B8DEE"),
                            steps=[
                                dict(range=[0, cap * 0.7], color="#E8F5E9"),
                                dict(range=[cap * 0.7, cap * 0.9], color="#FFF3CD"),
                                dict(range=[cap * 0.9, cap], color="#F8D7DA"),
                            ],
                            threshold=dict(
                                line=dict(color="#DC3545", width=3),
                                thickness=0.8,
                                value=cap,
                            ),
                        ),
                        title=dict(text="Spend"),
                    )
                )
                fig_gauge.update_layout(height=200, margin=dict(t=30, b=10, l=20, r=20))
                st.plotly_chart(fig_gauge, use_container_width=True)

            st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 7 — Jobs
# ─────────────────────────────────────────────────────────────────────────────
with tab_jobs:
    st.subheader("GSD Worker Jobs")

    if len(jobs_df) == 0:
        st.info("No jobs queued yet.")
    else:
        j_col1, j_col2 = st.columns(2)

        with j_col1:
            job_status_counts = jobs_df["status"].value_counts().reset_index()
            job_status_counts.columns = ["status", "count"]
            colour_map_j = {s: JOB_STATUS_COLOURS.get(s, "#999") for s in job_status_counts["status"]}
            fig_js = px.pie(
                job_status_counts,
                names="status",
                values="count",
                color="status",
                color_discrete_map=colour_map_j,
                title="Job Status",
                hole=0.4,
            )
            fig_js.update_layout(height=300, margin=dict(t=40, b=10))
            st.plotly_chart(fig_js, use_container_width=True)

        with j_col2:
            job_type_counts = jobs_df["job_type"].value_counts().reset_index()
            job_type_counts.columns = ["type", "count"]
            fig_jt = px.bar(
                job_type_counts,
                x="type",
                y="count",
                color="type",
                title="Jobs by Type",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_jt.update_layout(
                height=300,
                margin=dict(t=40, b=10),
                showlegend=False,
                xaxis_title="",
                yaxis_title="Count",
            )
            st.plotly_chart(fig_jt, use_container_width=True)

        # GSD pipeline visual
        st.markdown("#### 🔧 GSD Execution Pipeline")
        gsd_cols = st.columns(6)
        gsd_stages = [
            ("📚", "RESEARCH", "Gather context, read docs, understand requirements"),
            ("💻", "IMPLEMENT", "Generate code with Claude Sonnet"),
            ("🧪", "QA", "Run in Fly.io sandbox, execute tests"),
            ("🔍", "CRITIC", "Gemini adversarial review"),
            ("📝", "PR", "Create GitHub Pull Request"),
            ("📱", "GATE 4", "Telegram final approval"),
        ]
        for col, (icon, name, desc) in zip(gsd_cols, gsd_stages):
            col.markdown(
                f"""<div style="text-align:center; background:#1a1a2e; padding:16px 8px;
                border-radius:10px; border:1px solid #333;">
                <div style="font-size:2em;">{icon}</div>
                <div style="font-weight:bold; margin:6px 0;">{name}</div>
                <div style="font-size:0.8em; color:#999;">{desc}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("")

        # Job table
        st.dataframe(
            jobs_df.rename(
                columns={
                    "job_type": "Type",
                    "status": "Status",
                    "retry_count": "Retries",
                    "max_retries": "Max",
                    "deliverable": "Deliverable",
                    "created_at": "Created",
                    "updated_at": "Updated",
                }
            )[["Type", "Status", "Retries", "Max", "Deliverable", "Created", "Updated"]],
            use_container_width=True,
            hide_index=True,
        )

# ── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "Agency-in-a-Box · Autonomous AI Dev Agency · "
    "Dashboard powered by Streamlit + Plotly · "
    "Data from PostgreSQL"
)
