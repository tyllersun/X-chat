import streamlit as st
import pandas as pd
import numpy as np
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import time

# Import Mock APIs
from mock_api import (
    submit_chat_request, poll_chat_status, get_chat_result, db, 
    fetch_data, generate_universal_chart, generate_chart_insight
)

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

# Priority 1: Read from st.secrets (Streamlit Cloud deployment)
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

# Priority 2: Read from auth_config.yaml (local development)
elif os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as file:
        config = yaml.load(file, Loader=SafeLoader)

# Priority 3: Auto-generate default config file (first-time local setup only)
else:
    import bcrypt
    salt = bcrypt.gensalt()
    hashed_pwd = bcrypt.hashpw('admin123'.encode('utf8'), salt).decode('utf8')
    config = {
        'credentials': {
            'usernames': {
                'admin': {
                    'email': 'admin@example.com',
                    'failed_login_attempts': 0,
                    'logged_in': False,
                    'name': 'Admin',
                    'password': hashed_pwd
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
        yaml.dump(config, file, default_flow_style=False)

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
        # Let the user know if mock DB refreshed
        if db.check_for_updates():
            st.toast("Internal Data Source Updated!", icon="🔄")
            
        st.subheader("📊 Key Metrics")
        m1, m2, m3 = st.columns(3)

        # TODO [BACKEND API]: Fetch real-time KPI metrics from backend analytics service
        m1.metric("Total Users", "10,245", "+5.2%")
        m2.metric("Active Sessions", "1,203", "-1.5%")
        m3.metric("Revenue", "$45,231", "+12.3%")

        # TODO [BACKEND API]: AI insight text should be generated by LLM based on real KPI data
        st.info("💡 **AI Insight — Metrics**: Revenue grew 12.3% this week, primarily driven by Product B. Active sessions dipped slightly; consider investigating drop-off points in the funnel.")

        st.subheader("Weekly Activity Trend")

        # 1. Fetch Data
        trend_df = fetch_data(
            raw_data_source="sales_table",
            columns=["Date", "Product A", "Product B", "Product C"]
        )

        # 2. Use new Universal Chart API statelessly for Dashboard
        chart_res = generate_universal_chart(
             chart_type="line",
             data=trend_df,
             config={"title": "", "x": "Date", "y": ["Product A", "Product B", "Product C"]}
        )
        import plotly.graph_objects as go
        fig = go.Figure(chart_res["spec"])
        st.plotly_chart(fig, use_container_width=True)

        # 3. Get Cached Insight
        insight_key = f"dash_sales_insight_{id(trend_df)}"
        trend_insight = generate_chart_insight(insight_key, "line")
        st.info(f"💡 **AI Insight — Trend**: {trend_insight}")

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

            # 1. Fetch Data
            geo_df = fetch_data(
                raw_data_source="user_geo_table",
                columns=["lat", "lon"]
            )

            # 2. Use new Universal Chart API statelessly for Dashboard
            geo_res = generate_universal_chart(
                 chart_type="map",
                 data=geo_df,
                 config={"title": "", "lat": "lat", "lon": "lon"}
            )
            fig_geo = go.Figure(geo_res["spec"])
            st.plotly_chart(fig_geo, use_container_width=True)

            # 3. Get Cached Insight
            insight_key = f"dash_geo_insight_{id(geo_df)}"
            geo_insight = generate_chart_insight(insight_key, "map")
            st.success(f"🎯 **AI Insight — Distribution**: {geo_insight}")

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
        # Collapsible reasoning trace (shown above the response if available)
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

        for block in blocks:
            btype = block.get("type")

            if btype == "text":
                st.markdown(block["content"])

            elif btype == "plotly":
                # Preferred chart type: API returns a full Plotly figure dict (spec)
                # Supports 60+ chart types — line, bar, scatter, pie, heatmap, funnel, etc.
                import plotly.graph_objects as go
                import uuid
                with st.container(border=True):
                    fig = go.Figure(block["spec"])
                    # Use a unique key combining id and random uuid to prevent streamlit duplicate ID errors on cached repeated responses
                    chart_key = f"plotly_{id(block)}_{uuid.uuid4().hex[:8]}"
                    st.plotly_chart(fig, use_container_width=True, key=chart_key)
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

            elif btype == "reference":
                with st.expander("📚 References", expanded=False):
                    for src in block.get("sources", []):
                        title = src.get("title", "Unknown Source")
                        url = src.get("url")
                        snippet = src.get("snippet")
                        link_text = f"[{title}]({url})" if url else f"**{title}**"
                        st.markdown(f"**{link_text}**")
                        if snippet:
                            st.caption(f"> {snippet}")

    def _simulate_llm_response(prompt: str, chat_id: str, user_id: str):
        """
        Simulate an LLM response utilizing the asynchronous polling pattern mapping
        to the real world implementation of the api.
        """
        # 1. Submit request to get a Task ID
        request_id = submit_chat_request(prompt, chat_id, user_id)
        
        # 2. Poll the status endpoint until complete
        while True:
            status_res = poll_chat_status(request_id)
            if status_res["status"] == "complete":
                break
            # Yield the status message for the Streamlit UI to display
            yield status_res["message"]
            time.sleep(0.5) # Poll interval
            
        # 3. Task is complete, fetch the final result JSON
        final_result = get_chat_result(request_id)
        
        # Yield a sentinel dict at the end with the final result
        yield final_result

    def handle_user_input(prompt, current_title):
        """Process user input, show live status while LLM works, then render block response."""
        st.session_state.chat_history[current_title].append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            # Show a live status box while the async API is polling
            with st.status("🤖 Submitting request to AI...", expanded=True) as status:
                result = None
                user_id = st.session_state.get("username", "admin")
                for item in _simulate_llm_response(prompt, current_title, user_id):
                    if isinstance(item, str):
                        # Progress step message
                        st.write(item)
                    else:
                        # Final result dict
                        result = item
                status.update(label="✅ Done!", state="complete", expanded=False)

            # Render the block-structured response explicitly using the dictionary we just created
            render_message_blocks(result["blocks"], result.get("trace"))

        # Persist to chat history EXACTLY as it is rendered above so it matches on re-run
        st.session_state.chat_history[current_title].append({
            "role": "assistant",
            "blocks": result["blocks"],
            "trace":  result.get("trace"),
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
        
        # 1. Process Override Prompt immediately
        override_prompt = st.session_state.pop('chat_input_override', None)
        if override_prompt:
            st.session_state.chat_history[current_title].append({"role": "user", "content": override_prompt})
            
        messages = st.session_state.chat_history[current_title]
        
        # 1.5 Create an empty placeholder to securely clear the welcome UI
        welcome_placeholder = st.empty()
        
        # 2. Render UI
        if len(messages) == 0:
            with welcome_placeholder.container():
                st.write("")
                st.write("")
                st.write("")
                st.markdown("<h2 style='text-align: center; color: #888;'>How can I help you today?</h2>", unsafe_allow_html=True)
                st.write("")
                
                col1, col2 = st.columns(2)
                with col1:
                    # Use standard buttons without deprecation warning use_container_width
                    if st.button("📊 Show this week's product trends"):
                        st.session_state['chat_input_override'] = "Show this week's product trends"
                        st.rerun()
                    if st.button("👥 Analyze user activity"):
                        st.session_state['chat_input_override'] = "Analyze user activity"
                        st.rerun()
                    if st.button("📄 Ask about remote work policy"):
                        st.session_state['chat_input_override'] = "What is the remote work policy?"
                        st.rerun()
                with col2:
                    if st.button("🗺️ Show user geographic distribution map"):
                        st.session_state['chat_input_override'] = "Show user geographic distribution map"
                        st.rerun()
                    if st.button("💰 Predict next month's revenue"):
                        st.session_state['chat_input_override'] = "Predict next month's revenue"
                        st.rerun()
        else:
            # Forcefully clear the welcome placeholder if there are messages
            welcome_placeholder.empty()
            for msg in messages:
                with st.chat_message(msg["role"]):
                    if "blocks" in msg:
                        # New block-based format (supports inline charts + trace)
                        render_message_blocks(msg["blocks"], msg.get("trace"))
                    else:
                        # Legacy plain-text format (backward compatible)
                        st.markdown(msg.get("content", ""))
                    
        # 3. Handle processing for the newly added prompt (either from override or just typed)
        if len(messages) > 0 and messages[-1]["role"] == "user":
            prompt = messages[-1]["content"]
            st.session_state.chat_history[current_title].pop()
            handle_user_input(prompt, current_title)
            st.rerun()
            
        elif prompt := st.chat_input("Ask a question (e.g., 'show product trends' or 'user distribution map')"):
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
