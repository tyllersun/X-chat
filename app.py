import streamlit as st
import pandas as pd
import numpy as np
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import time
import os

import requests
# ============================================================
# API Config
# Priority: st.secrets (Streamlit Cloud) → hardcoded fallback (local dev)
# ============================================================
LLM_API_URL = st.secrets.get("LLM_API_URL", "https://xchat-llm-api-574222557748.asia-east1.run.app")
XCHAT_HISTORY_API = st.secrets.get("XCHAT_HISTORY_API", "http://localhost:8003")  # History API
API_KEY = st.secrets.get("API_KEY", "please use api key")
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY
}

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
    # History Helper Functions
    # ----------------------------------------------------------
    import json
    LOCAL_HISTORY_DIR = "local_history"
    os.makedirs(LOCAL_HISTORY_DIR, exist_ok=True)

    def load_chat_history(user_id):
        try:
            # Try to get from API (sync)
            resp = requests.get(f"{XCHAT_HISTORY_API}/v1/history/{user_id}", headers=HEADERS, timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                return data["chat_history"], data["current_chat"]
        except Exception:
            pass
        
        file_path = os.path.join(LOCAL_HISTORY_DIR, f"{user_id}.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data["chat_history"], data.get("current_chat", "New Chat 1")
                
        return {
            "New Chat 1": [],
            "Product Analysis (Example)": [
                {"role": "user", "content": "I'd like to see the retention rate for Product C"},
                {"role": "assistant", "content": "Here is the retention analysis for Product C last month:\n- Week 1: 45%\n- Week 4: 20%"}
            ]
        }, "New Chat 1"

    def save_chat_history():
        user_id = st.session_state.get("username", "admin")
        payload = {
            "current_chat": st.session_state.current_chat, 
            "chat_history": st.session_state.chat_history
        }
        
        file_path = os.path.join(LOCAL_HISTORY_DIR, f"{user_id}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

        # Try background sync
        try:
            requests.post(f"{XCHAT_HISTORY_API}/v1/history/{user_id}", json=payload, headers=HEADERS, timeout=1.5)
        except Exception:
            pass

    # ----------------------------------------------------------
    # Session State Initialization
    # ----------------------------------------------------------
    if "chat_history" not in st.session_state or "current_chat" not in st.session_state:
        current_user = st.session_state.get("username", "admin")
        loaded_history, loaded_current = load_chat_history(current_user)
        st.session_state.chat_history = loaded_history
        st.session_state.current_chat = loaded_current

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
        
        # We put the toggles in a nested layout for better alignment
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            is_ai_mode = st.toggle(
                "🤖 AI Mode", 
                value=False, 
                help="Turn ON for AI chat, turn OFF for dashboard"
            )
        with t_col2:
            use_real_llm = st.toggle(
                "🚀 Real LLM",
                value=False,
                help="Turn ON to connect to Cloud Run LLM API",
                disabled=not is_ai_mode,
                key="use_real_llm"
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
                # Build a CSS-styled vertical pipeline
                # We use a single string without indentation to avoid Streamlit/Markdown code block interpretation
                pipeline_html = "<div style='margin-left: 15px; border-left: 2px solid #4B5563; padding-left: 20px; padding-top: 10px; font-family: ui-sans-serif, system-ui, -apple-system, blinkmacsystemfont, \"Segoe UI\", roboto, \"Helvetica Neue\", arial, sans-serif;'>"
                for idx, step in enumerate(trace):
                    icon = {
                        "llm_call":  "🧠",
                        "tool_call": "🔧",
                        "sub_agent": "🤖",
                        "query":     "🗄️",
                    }.get(step.get("type", ""), "•")
                    
                    dur = step.get("duration_ms")
                    dur_str = f"<span style='color: #9CA3AF; font-size: 0.85em; margin-left: 8px;'>{dur}ms</span>" if dur else ""
                    
                    detail = step.get("detail", "")
                    detail_html = f"<div style='color: #9CA3AF; font-size: 0.85em; margin-top: 4px; line-height: 1.4;'>{detail}</div>" if detail else ""
                    
                    # Highlight the labels to look more premium
                    label_color = "#E5E7EB"
                    if step.get("type") == "tool_call":
                        label_color = "#60A5FA" # Blue-ish for tools
                    
                    # Connection node (circle with icon)
                    node_style = "position: absolute; left: -32px; top: -2px; width: 24px; height: 24px; background: #1F2937; border: 1px solid #4B5563; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.9em; z-index: 10;"
                    
                    pipeline_html += f"<div style='position: relative; margin-bottom: 25px;'><span style='{node_style}'>{icon}</span><div style='font-weight: 600; color: {label_color}; display: flex; align-items: center;'>{step['label']} {dur_str}</div>{detail_html}</div>"
                
                pipeline_html += "</div>"
                st.markdown(pipeline_html, unsafe_allow_html=True)

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
        Or call the real Cloud Run LLM API if 'use_real_llm' is true.
        """
        use_real = st.session_state.get("use_real_llm", False)
        
        if use_real:
            # --- REAL LLM API PATH ---
            # Format history to match ChatMessage model (only 'role' and 'content')
            formatted_history = []
            for msg in st.session_state.chat_history.get(chat_id, [])[:-1]:
                content = msg.get("content", "")
                if not content and "blocks" in msg:
                    # If this is an assistant message with blocks, extract text
                    content = "\n".join(b["content"] for b in msg["blocks"] if b.get("type") == "text")
                formatted_history.append({"role": msg["role"], "content": content})
                
            payload = {
                "prompt": prompt,
                "user_id": user_id,
                "chat_id": chat_id,
                "history": formatted_history,
                # Pass login info so personalization_tool can use it
                "user_info": {
                    "username": st.session_state.get("username"),
                    "name": st.session_state.get("name"),
                    "email": st.session_state.get("email"),
                }
            }
            try:
                # 1. Submit request
                resp = requests.post(f"{LLM_API_URL}/v1/chat/submit", json=payload, headers=HEADERS, timeout=10)
                resp.raise_for_status()
                request_id = resp.json()["request_id"]
                
                # 2. Poll the status
                while True:
                    status_resp = requests.get(f"{LLM_API_URL}/v1/chat/status/{request_id}", headers=HEADERS, timeout=10)
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    
                    if status_data["status"] == "complete":
                        break
                    elif status_data["status"] == "failed":
                        yield {"blocks": [{"type": "text", "content": f"❌ API Error: {status_data.get('message', 'Unknown error')} "}], "trace": []}
                        return
                        
                    yield status_data["message"]
                    time.sleep(1.0)
                    
                # 3. Get result
                res_resp = requests.get(f"{LLM_API_URL}/v1/chat/result/{request_id}", headers=HEADERS, timeout=15)
                res_resp.raise_for_status()
                yield res_resp.json()
                
            except Exception as e:
                yield {"blocks": [{"type": "text", "content": f"❌ Error connecting to Real LLM API: {str(e)}"}], "trace": []}
                
        else:
            # --- MOCK API PATH ---
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
        is_first_message = len(st.session_state.chat_history[current_title]) == 0 and current_title.startswith("New Chat")
        
        st.session_state.chat_history[current_title].append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            # Show a live status box while the async API is polling
            with st.status("🤖 Submitting request to AI...", expanded=True) as status:
                result = None
                user_id = st.session_state.get("username", "admin")
                for item in _simulate_llm_response(prompt, current_title, user_id):
                    if isinstance(item, str):
                        # Progress step message
                        # Update the status label directly instead of appending with st.write
                        status.update(label=f"🤖 {item}")
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

        if is_first_message:
            # Generate new title from prompt (e.g. first 15 chars)
            new_title = prompt[:15] + "..." if len(prompt) > 15 else prompt
            # Handle duplicates
            base_new_title = new_title
            counter = 1
            while new_title in st.session_state.chat_history and new_title != current_title:
                new_title = f"{base_new_title} ({counter})"
                counter += 1
                
            new_history = {}
            for k, v in st.session_state.chat_history.items():
                if k == current_title:
                    new_history[new_title] = v
                else:
                    new_history[k] = v
            st.session_state.chat_history = new_history
            st.session_state.current_chat = new_title

        save_chat_history()

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
                save_chat_history()
                st.session_state['close_sidebar_flag'] = True
                st.rerun()    
            st.markdown("---")
            for chat_title in reversed(list(st.session_state.chat_history.keys())):
                btn_type = "primary" if chat_title == st.session_state.current_chat else "secondary"
                if st.button(f"💬 {chat_title}", key=f"btn_{chat_title}", use_container_width=True, type=btn_type):
                    st.session_state.current_chat = chat_title
                    save_chat_history()
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
