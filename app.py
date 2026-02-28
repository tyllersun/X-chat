import streamlit as st
import pandas as pd
import numpy as np
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="X-chat Assistant", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# Custom CSS: hide default Streamlit menu/footer, replace sidebar toggle with hamburger icon
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Replace sidebar expand button ">" with hamburger "☰" */
    button[kind="header"] {
        color: transparent !important;
    }
    button[kind="header"]::before {
        content: "☰";
        color: var(--text-color);
        font-size: 24px;
        position: absolute;
        left: 50%;
        transform: translateX(-50%);
    }
    /* Replace sidebar close button with "✕" */
    section[data-testid="stSidebar"] button[kind="header"]::before {
        content: "✕";
        font-size: 20px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Helper: Close Sidebar via JS injection
# ============================================================
# Streamlit doesn't expose a Python API to collapse the sidebar.
# We inject JS via st.components.v1.html (sandboxed iframe with allow-same-origin)
# which can access window.parent.document to click the collapse button.
import uuid
def trigger_sidebar_close():
    # Generate a unique ID so Streamlit doesn't cache/skip this component on re-render
    unique_id = uuid.uuid4().hex[:8]
    js = f"""
    <div id="sidebar-closer-{unique_id}" style="display:none"></div>
    <script>
        (function() {{
            var attempt = 0;
            var maxAttempts = 10;
            function tryClose() {{
                attempt++;
                var doc = window.parent.document;
                // Try primary selector (Streamlit data-testid)
                var btn = doc.querySelector('button[data-testid="stSidebarCollapseButton"]');
                // Fallback: aria-label
                if (!btn) btn = doc.querySelector('button[aria-label="Collapse sidebar"]');
                // Fallback: any button inside the sidebar header area
                if (!btn) btn = doc.querySelector('section[data-testid="stSidebar"] button');
                if (btn) {{
                    btn.click();
                }} else if (attempt < maxAttempts) {{
                    setTimeout(tryClose, 150);
                }}
            }}
            setTimeout(tryClose, 300);
        }})();
    </script>
    """
    st.components.v1.html(js, height=0, width=0)


# ============================================================
# Authentication Setup
# ============================================================
CONFIG_FILE = 'auth_config.yaml'

if not os.path.exists(CONFIG_FILE):
    hashed_passwords = stauth.Hasher.hash_passwords(['admin123'])
    default_config = {
        'credentials': {
            'usernames': {
                'admin': {
                    'email': 'admin@example.com',
                    'failed_login_attempts': 0,
                    'logged_in': False,
                    'name': 'Admin',
                    'password': hashed_passwords[0]
                }
            }
        },
        'cookie': {
            'expiry_days': 30,
            'key': 'some_signature_key',
            'name': 'xchat_cookie'
        }
    }
    with open(CONFIG_FILE, 'w') as file:
        yaml.dump(default_config, file, default_flow_style=False)

if "credentials" in st.secrets:
    config = dict(st.secrets)
    if "credentials" in config:
        config["credentials"] = dict(config["credentials"])
        if "usernames" in config["credentials"]:
            config["credentials"]["usernames"] = {
                k: dict(v) for k, v in config["credentials"]["usernames"].items()
            }
    if "cookie" in config:
        config["cookie"] = dict(config["cookie"])
else:
    with open(CONFIG_FILE) as file:
        config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

try:
    authenticator.login()
except Exception as e:
    st.error(e)

if st.session_state["authentication_status"] is False:
    st.error('Incorrect username or password')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')

# ============================================================
# Main App (only visible after successful login)
# ============================================================
if st.session_state["authentication_status"]:
    
    with st.sidebar:
        # Sidebar: welcome + logout
        st.write(f'Welcome back, *{st.session_state["name"]}*')
        authenticator.logout('Logout', 'sidebar')

    # ----------------------------------------------------------
    # Session State Initialization
    # ----------------------------------------------------------
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = {
            "New Chat 1": [],
            "Product Analysis (Example)": [
                {"role": "user", "content": "I'd like to see the retention rate for Product C"},
                {"role": "assistant", "content": "Here is the retention analysis for Product C last month:\n- Week 1: 45%\n- Week 4: 20%"}
            ]
        }
    if "current_chat" not in st.session_state:
        st.session_state.current_chat = "New Chat 1"

    if "normal_view" not in st.session_state:
        st.session_state.normal_view = "Dashboard"

    # ----------------------------------------------------------
    # Header & Mode Toggle (top-right)
    # ----------------------------------------------------------
    col_title, col_toggle = st.columns([7, 3])
    with col_title:
        st.title("X-chat Data Platform")
    with col_toggle:
        st.write("") 
        is_ai_mode = st.toggle(
            "🤖 AI Assistant Mode", 
            value=False, 
            help="Turn ON for AI chat, turn OFF for traditional dashboard"
        )

    st.markdown("---")

    # Fire sidebar close JS in the MAIN area (not inside sidebar) for reliable execution
    if st.session_state.get('close_sidebar_flag', False):
        trigger_sidebar_close()
        st.session_state['close_sidebar_flag'] = False

    # ==========================================================
    # Normal Mode Views
    # ==========================================================
    def render_dashboard():
        st.subheader("📊 Key Metrics")
        m1, m2, m3 = st.columns(3)

        # TODO [BACKEND API]: Fetch real-time KPI metrics from backend analytics service
        m1.metric("Total Users", "10,245", "+5.2%")
        m2.metric("Active Sessions", "1,203", "-1.5%")
        m3.metric("Revenue", "$45,231", "+12.3%")

        # TODO [BACKEND API]: AI insight text should be generated by LLM based on real KPI data
        st.info("💡 **AI Insight — Metrics**: Revenue grew 12.3% this week, primarily driven by Product B. Active sessions dipped slightly; consider investigating drop-off points in the funnel.")

        st.subheader("Weekly Activity Trend")

        # TODO [BACKEND API]: Replace with real time-series from data warehouse
        chart_data = pd.DataFrame(
            np.random.randn(20, 3) * 10 + 50,
            columns=['Product A', 'Product B', 'Product C']
        )
        st.line_chart(chart_data)

        # TODO [BACKEND API]: AI insight text should be generated by LLM based on trend data
        st.info("💡 **AI Insight — Trend**: Product B shows a consistent upward trend over the past 20 days. Product A appears to be plateauing — may need a new campaign push.")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Recent Transactions")

            # TODO [BACKEND API]: Fetch paginated transaction records from backend database
            df = pd.DataFrame({
                'Date': pd.date_range(start='2026/02/01', periods=5),
                'Amount': [100, 250, 50, 400, 120],
                'Status': ['Completed', 'Pending', 'Completed', 'Failed', 'Completed']
            })
            st.dataframe(df, width='stretch')

            # TODO [BACKEND API]: AI insight text should be generated by LLM based on transaction data
            st.warning("⚠️ **AI Insight — Transactions**: 1 failed transaction detected in the past 5 records. Failure rate is within normal range, but worth monitoring if frequency increases.")

        with c2:
            st.subheader("User Geographic Distribution")

            # TODO [BACKEND API]: Fetch real user geo-coordinates from user analytics service
            dist_data = pd.DataFrame(
                np.random.randn(100, 2) / [50, 50] + [25.033, 121.565],
                columns=['lat', 'lon']
            )
            st.map(dist_data)

            # TODO [BACKEND API]: AI insight text should be generated by LLM based on geo data
            st.success("🎯 **AI Insight — Distribution**: 68% of users are concentrated in the northern metro area. Consider targeted campaigns in central and southern regions to expand reach.")

    def render_introduction():
        st.subheader("📖 System Introduction")
        st.markdown("""
        Welcome to **X-chat Data Platform**! A next-gen data tool combining AI chatbot capabilities with traditional Business Intelligence (BI).
        
        ### 🌟 Core Features
        * **Normal Mode**: Traditional menu-driven navigation — dashboards, schedules, and more.
        * **AI Mode**: Conversational interface powered by LLM. Ask questions in natural language and receive charts + insights.
        
        ### 🎯 Vision
        "Make data access as natural as talking to a colleague."
        
        ---
        *Version: v1.0.0-beta*  
        *Last updated: 2026-02-27*
        """)

    def render_schedule():
        st.subheader("📅 Project Schedule")
        schedule_df = pd.DataFrame({
            "Task": ["Platform Infrastructure", "Dashboard UI Polish", "AI Model Integration", "Beta Testing", "Production Launch"],
            "Owner": ["Alice", "Bob", "Charlie", "Team", "Team"],
            "Status": ["✅ Done", "✅ Done", "🔄 In Progress", "⏳ Pending", "⏳ Pending"],
            "Target Date": ["2026-02-15", "2026-02-28", "2026-03-10", "2026-03-25", "2026-04-01"]
        })
        st.dataframe(schedule_df, hide_index=True, width='stretch')
        st.info("💡 Currently in the 'AI Model Integration' phase, expected completion by mid-March.")

    import time

    # ==========================================================
    # AI Mode Functions
    # ==========================================================

    def render_message_blocks(blocks: list, trace: list = None):
        """
        Render a list of mixed content blocks inline within a chat message.
        Supported block types: text, chart, bar_chart, map, metric
        """
        for block in blocks:
            btype = block.get("type")

            if btype == "text":
                st.markdown(block["content"])

            elif btype == "plotly":
                # Preferred chart type: API returns a full Plotly figure dict (spec)
                # Supports 60+ chart types — line, bar, scatter, pie, heatmap, funnel, etc.
                import plotly.graph_objects as go
                with st.container(border=True):
                    fig = go.Figure(block["spec"])
                    st.plotly_chart(fig, use_container_width=True)
                    if block.get("insight"):
                        st.info(f"💡 **AI Insight**: {block['insight']}")

            elif btype == "chart":
                # Legacy: simple line chart via st.line_chart (kept for backward compat)
                with st.container(border=True):
                    if block.get("title"):
                        st.markdown(f"#### {block['title']}")
                    df = pd.DataFrame(block["data"])
                    st.line_chart(df)
                    if block.get("insight"):
                        st.info(f"💡 **AI Insight**: {block['insight']}")

            elif btype == "bar_chart":
                # Legacy: simple bar chart via st.bar_chart (kept for backward compat)
                with st.container(border=True):
                    if block.get("title"):
                        st.markdown(f"#### {block['title']}")
                    df = pd.DataFrame(block["data"])
                    st.bar_chart(df)
                    if block.get("insight"):
                        st.info(f"💡 **AI Insight**: {block['insight']}")

            elif btype == "map":
                with st.container(border=True):
                    if block.get("title"):
                        st.markdown(f"#### {block['title']}")
                    df = pd.DataFrame(block["data"])
                    st.map(df)
                    if block.get("insight"):
                        st.success(f"🎯 **AI Insight**: {block['insight']}")

            elif btype == "metric":
                cols = st.columns(len(block["metrics"]))
                for col, m in zip(cols, block["metrics"]):
                    col.metric(m["label"], m["value"], m.get("delta"))

        # Collapsible reasoning trace (shown below the response if available)
        if trace:
            with st.expander("🔍 View reasoning trace", expanded=False):
                for step in trace:
                    icon = {
                        "llm_call":  "🧠",
                        "tool_call": "🔧",
                        "sub_agent": "🤖",
                        "query":     "🗄️",
                    }.get(step.get("type", ""), "•")
                    dur = step.get("duration_ms")
                    dur_str = f" — `{dur} ms`" if dur else ""
                    st.markdown(f"{icon} **{step['label']}**{dur_str}")
                    if step.get("detail"):
                        st.caption(step["detail"])

    def _simulate_llm_response(prompt: str):
        """
        Simulate an LLM response with tool-call steps and a structured block response.
        In production, replace the time.sleep loop with polling a backend status endpoint.

        # TODO [BACKEND API]: Replace this entire function with:
        #   1. POST /v1/chat/submit  → get request_id
        #   2. Poll GET /v1/chat/status/{request_id} every 500ms (replace time.sleep steps)
        #   3. GET /v1/chat/result/{request_id}  → get blocks + trace
        """
        want_chart = any(k in prompt.lower() for k in ["trend", "趨勢", "圖", "chart", "sales"])
        want_map   = any(k in prompt.lower() for k in ["map", "地圖", "分佈", "distribution"])

        # --- Simulated thinking steps (replace with real status polling in production) ---
        steps = [
            ("🧠", "Understanding your question...",         0.6),
        ]
        if want_chart:
            steps += [
                ("🔧", "Calling tool: `query_sales_trend(30d)`", 0.8),
                ("🗄️", "Query returned 30 rows from database",  0.5),
                ("🧠", "Generating AI insight from data...",    0.7),
            ]
        elif want_map:
            steps += [
                ("🔧", "Calling tool: `query_user_geo_data()`", 0.8),
                ("🗄️", "Retrieved 1,240 user coordinates",     0.5),
                ("🧠", "Analysing regional distribution...",   0.7),
            ]
        else:
            steps += [
                ("🧠", "Searching knowledge base...",          0.5),
                ("🤖", "Routing to general-answer sub-agent",  0.6),
            ]

        # Yield each step so the caller can display it progressively
        for icon, msg, delay in steps:
            yield f"{icon} {msg}"
            time.sleep(delay)

        # --- Build final structured response blocks ---
        if want_chart:
            blocks = [
                {"type": "text", "content": f"Here is the product trend analysis for your query: *'{prompt}'*"},
                {
                    "type": "chart",
                    "title": "📈 30-Day Sales Trend",
                    "data": {
                        "Product A": (np.random.randn(30) * 5 + 60).tolist(),
                        "Product B": (np.random.randn(30) * 5 + 70).tolist(),
                        "Product C": (np.random.randn(30) * 5 + 50).tolist(),
                    },
                    "insight": "Product B shows the strongest upward trajectory over the last 30 days. Consider increasing marketing investment there.",
                },
                {"type": "text", "content": "Would you like a deeper breakdown by region or user segment?"},
            ]
            trace = [
                {"type": "llm_call",  "label": "Intent detection",              "duration_ms": 310},
                {"type": "tool_call", "label": "query_sales_trend(period=30d)",  "duration_ms": 820, "detail": "Returned 30 rows from BigQuery"},
                {"type": "llm_call",  "label": "Insight generation",             "duration_ms": 540},
            ]
        elif want_map:
            blocks = [
                {"type": "text", "content": f"Here is the user geographic distribution for: *'{prompt}'*"},
                {
                    "type": "map",
                    "title": "🗺️ User Geographic Distribution",
                    "data": (
                        pd.DataFrame(np.random.randn(80, 2) / [40, 40] + [25.033, 121.565], columns=["lat", "lon"])
                        .to_dict(orient="records")
                    ),
                    "insight": "68% of users are concentrated in the northern metropolitan area. Strong growth potential in the south.",
                },
                {"type": "text", "content": "Would you like to filter by user segment (new / active / churned)?"},
            ]
            trace = [
                {"type": "llm_call",  "label": "Intent detection",             "duration_ms": 295},
                {"type": "tool_call", "label": "query_user_geo_data()",         "duration_ms": 760, "detail": "Retrieved 1,240 coordinates from Users DB"},
                {"type": "sub_agent", "label": "Regional clustering sub-agent", "duration_ms": 430, "detail": "Identified 3 primary clusters"},
                {"type": "llm_call",  "label": "Insight generation",            "duration_ms": 510},
            ]
        else:
            blocks = [
                {"type": "text", "content": f"I received your message: *'{prompt}'*."},
                {"type": "text", "content": "Try asking about **product trends** or **user distribution map** to see the chart generation in action."},
            ]
            trace = [
                {"type": "llm_call",  "label": "Intent detection",          "duration_ms": 280},
                {"type": "sub_agent", "label": "General-answer sub-agent",  "duration_ms": 610},
            ]

        # Yield a sentinel dict at the end with the final result
        yield {"blocks": blocks, "trace": trace}

    def handle_user_input(prompt, current_title):
        """Process user input, show live status while LLM works, then render block response."""
        st.session_state.chat_history[current_title].append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            # Show a live status box while the (simulated) LLM is working
            with st.status("🤖 AI is analysing your request...", expanded=True) as status:
                result = None
                for item in _simulate_llm_response(prompt):
                    if isinstance(item, str):
                        # Progress step message
                        st.write(item)
                    else:
                        # Final result dict
                        result = item
                status.update(label="✅ Done!", state="complete", expanded=False)

            # Render the block-structured response
            render_message_blocks(result["blocks"], result["trace"])

        # Persist to chat history
        st.session_state.chat_history[current_title].append({
            "role": "assistant",
            "blocks": result["blocks"],
            "trace":  result["trace"],
        })

    @st.dialog("💬 Send Feedback")
    def feedback_dialog(mode_key: str):
        """Floating modal dialog for feedback — opened by the sidebar button."""
        st.markdown("How would you rate your experience?")
        rating = st.feedback("stars", key=f"fb_rating_{mode_key}")

        st.markdown("&nbsp;", unsafe_allow_html=True)
        msg = st.text_area(
            "Message (optional)",
            placeholder="Tell us what you think...",
            key=f"fb_msg_{mode_key}",
            height=100,
        )

        # Push Submit to the bottom with some spacing
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Submit", key=f"fb_submit_{mode_key}", use_container_width=True, type="primary"):
            if rating is None:
                st.warning("Please select a star rating first.")
            else:
                # TODO [BACKEND API]: POST /v1/feedback { user_id, rating, message, timestamp }
                if "feedback_log" not in st.session_state:
                    st.session_state.feedback_log = []
                st.session_state.feedback_log.append({
                    "rating": rating + 1,
                    "message": msg.strip(),
                    "user": st.session_state.get("name", "unknown"),
                })
                st.toast(f"Thanks for your feedback! {'⭐' * (rating + 1)}", icon="✅")
                st.rerun()  # closes the dialog

    def render_feedback_section(mode_key: str):
        """Render a single button at the bottom of the sidebar that opens the feedback dialog."""
        st.markdown("---")
        if st.button("💬 Feedback", key=f"fb_open_{mode_key}", use_container_width=True):
            feedback_dialog(mode_key)



    def render_ai_sidebar():
        with st.sidebar:
            st.write("")
            st.markdown("### 📝 Chat History")
            if st.button("➕ New Chat", use_container_width=True):
                new_title = f"New Chat {len(st.session_state.chat_history) + 1}"
                st.session_state.chat_history[new_title] = []
                st.session_state.current_chat = new_title
                st.session_state['close_sidebar_flag'] = True
                st.rerun()    
            st.markdown("---")
            for chat_title in reversed(list(st.session_state.chat_history.keys())):
                btn_type = "primary" if chat_title == st.session_state.current_chat else "secondary"
                if st.button(f"💬 {chat_title}", key=f"btn_{chat_title}", use_container_width=True, type=btn_type):
                    st.session_state.current_chat = chat_title
                    st.session_state['close_sidebar_flag'] = True
                    st.rerun()

            # Feedback section pinned to the bottom of the AI sidebar
            render_feedback_section(mode_key="ai")

    def render_ai_chat_mode():
        current_title = st.session_state.current_chat
        messages = st.session_state.chat_history[current_title]
        
        if len(messages) == 0:
            st.write("")
            st.write("")
            st.write("")
            st.markdown("<h2 style='text-align: center; color: #888;'>How can I help you today?</h2>", unsafe_allow_html=True)
            st.write("")
            
            col1, col2 = st.columns(2)
            with col1:
                # Use standard buttons without deprecation warning use_container_width
                if st.button("📊 Show this week's product trends"):
                    handle_user_input("Show this week's product trends", current_title)
                    st.rerun()
                if st.button("👥 Analyze user activity"):
                    handle_user_input("Analyze user activity", current_title)
                    st.rerun()
            with col2:
                if st.button("🗺️ Show user geographic distribution map"):
                    handle_user_input("Show user geographic distribution map", current_title)
                    st.rerun()
                if st.button("💰 Predict next month's revenue"):
                    handle_user_input("Predict next month's revenue", current_title)
                    st.rerun()
        else:
            for msg in messages:
                with st.chat_message(msg["role"]):
                    if "blocks" in msg:
                        # New block-based format (supports inline charts + trace)
                        render_message_blocks(msg["blocks"], msg.get("trace"))
                    else:
                        # Legacy plain-text format (backward compatible)
                        st.markdown(msg.get("content", ""))
                    
        if prompt := st.chat_input("Ask a question (e.g., 'show product trends' or 'user distribution map')"):
            handle_user_input(prompt, current_title)
            st.rerun()

    def render_normal_sidebar():
        with st.sidebar:
            st.write("") 
            views = ["Dashboard", "Introduction", "Schedule"]
            icons = ["📊", "📖", "📅"]
            for view, icon in zip(views, icons):
                btn_type = "primary" if st.session_state.normal_view == view else "secondary"
                if st.button(f"{icon} {view}", key=f"nav_{view}", use_container_width=True, type=btn_type):
                    st.session_state.normal_view = view
                    st.session_state['close_sidebar_flag'] = True
                    st.rerun()

            # Feedback section pinned to the bottom of the Normal sidebar
            render_feedback_section(mode_key="normal")

    # ==========================================================
    # Main Layout Router
    # ==========================================================
    if is_ai_mode:
        render_ai_sidebar()
        render_ai_chat_mode()
    else:
        render_normal_sidebar()
        
        selected_view = st.session_state.normal_view
        if selected_view == "Dashboard":
            render_dashboard()
        elif selected_view == "Introduction":
            render_introduction()
        elif selected_view == "Schedule":
            render_schedule()
