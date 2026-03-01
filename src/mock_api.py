# src/mock_api.py
import time
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, Generator

# ============================================================
# Mock Backend Store (Simulates Database and Cache)
# ============================================================
class MockDatabase:
    """Simulates a database that updates occasionally."""
    def __init__(self):
        self._last_update_time = time.time()
        self._sales_data = None
        self._geo_data = None
        self._generate_data()

    def _generate_data(self):
        """Generates fresh mock data."""
        # Sales Trend Data
        dates = pd.date_range(end=pd.Timestamp.today(), periods=30)
        self._sales_data = pd.DataFrame({
            "Date": dates,
            "Product A": np.random.randn(30) * 5 + 60,
            "Product B": np.random.randn(30) * 5 + 70,
            "Product C": np.random.randn(30) * 5 + 50,
        })
        
        # Geo Data
        self._geo_data = pd.DataFrame(
            np.random.randn(100, 2) / [50, 50] + [25.033, 121.565],
            columns=['lat', 'lon']
        )
        self._last_update_time = time.time()

    def check_for_updates(self) -> bool:
        """Simulate checking if data has changed (10% chance to update)."""
        if np.random.random() < 0.1:
            print("[MockDB] Data source updated!")
            self._generate_data()
            return True
        return False

    def get_sales_data(self) -> pd.DataFrame:
        return self._sales_data

    def get_geo_data(self) -> pd.DataFrame:
        return self._geo_data

# Global instance
db = MockDatabase()

# Global Cache Stores
_DATA_CACHE: Dict[str, pd.DataFrame] = {}
_INSIGHT_CACHE: Dict[str, str] = {}

# ============================================================
# 1. Data Fetch API (Stateful, Caching, Processing)
# ============================================================
def fetch_data(
    raw_data_source: str,
    columns: list = None,
    filters: list = None,
    groupby: list = None,
    aggregation: dict = None
) -> pd.DataFrame:
    """Mock implementation of POST /v1/data/fetch"""
    global _DATA_CACHE
    
    # Create cache key
    cache_key = f"{raw_data_source}|{'-'.join(columns or [])}|{str(filters)}|{str(groupby)}|{str(aggregation)}"
    
    data_updated = db.check_for_updates()
    
    if not data_updated and cache_key in _DATA_CACHE:
        print(f"[Data API] Cache HIT for {cache_key}")
        time.sleep(0.05) # Fast cache return
        return _DATA_CACHE[cache_key].copy()
        
    print(f"[Data API] Cache MISS or DATA UPDATED. Fetching and processing...")
    time.sleep(0.8) # Simulate DB query and processing
    
    if raw_data_source == "sales_table":
        df = db.get_sales_data()
    elif raw_data_source == "user_geo_table":
        df = db.get_geo_data()
    else:
        df = pd.DataFrame()

    # Mocking processing logic
    if columns:
        valid_cols = [c for c in columns if c in df.columns]
        if valid_cols:
            df = df[valid_cols]
            
    # Save to cache
    _DATA_CACHE[cache_key] = df.copy()
    return df

# ============================================================
# 2. Universal Chart Generation API (Stateless Rendering)
# ============================================================
def generate_universal_chart(
    chart_type: str,
    data: pd.DataFrame,
    config: dict
) -> Dict[str, Any]:
    """
    Mock implementation of POST /v1/charts/generate
    Completely stateless. Takes data and returns Plotly spec.
    """
    print(f"[Chart API] Generating {chart_type} chart statelessly...")
    time.sleep(0.1) # Fast rendering step
    result = {"spec": {}}
    
    if chart_type == "line":
        fig = go.Figure()
        y_cols = config.get("y", [])
        x_col = config.get("x", "Date")
        for col in y_cols:
            if col in data.columns and x_col in data.columns:
                fig.add_trace(go.Scatter(x=data[x_col], y=data[col], mode='lines', name=col))
        fig.update_layout(title=config.get("title", "Line Chart"), template="plotly_white")
        result["spec"] = json.loads(fig.to_json())
            
    elif chart_type == "map":
        lat_col = config.get("lat", "lat")
        lon_col = config.get("lon", "lon")
        if lat_col in data.columns and lon_col in data.columns:
            fig = go.Figure(go.Scattergeo(
                lon = data[lon_col],
                lat = data[lat_col],
                mode = 'markers',
                marker = dict(size = 8, color = 'blue', opacity = 0.8)
            ))
            fig.update_layout(
                title = config.get("title", 'Map Distribution'),
                geo_scope='asia',
                template="plotly_white"
            )
            result["spec"] = json.loads(fig.to_json())
            
    else:
        fig = go.Figure()
        fig.update_layout(title="Unknown Chart Type")
        result["spec"] = json.loads(fig.to_json())

    return result

# ============================================================
# 3. AI Insight Generation API (Stateful, Caching)
# ============================================================
def generate_chart_insight(data_hash_key: str, chart_type: str) -> str:
    """Mock API to generate LLM insights based on data, with caching."""
    global _INSIGHT_CACHE
    
    if data_hash_key in _INSIGHT_CACHE:
        print(f"[Insight API] Cache HIT for insight")
        return _INSIGHT_CACHE[data_hash_key]
        
    print(f"[Insight API] Cache MISS. Generating expensive LLM insight...")
    time.sleep(1.0) # Simulate expensive LLM call
    
    if chart_type == "line":
        insight = "Generated from raw sales_table. Product B remains strong compared to others."
    elif chart_type == "map":
        insight = "Generated from user_geo_table. Dense clustering near metropolitan areas."
    else:
        insight = "No specific insight available for this data."
        
    _INSIGHT_CACHE[data_hash_key] = insight
    return insight

# ============================================================
# 2. AI Chat API (Simulated Async Polling)
# ============================================================

# In-memory store for chat tasks (Job Queue)
_CHAT_TASKS = {}
import uuid

def submit_chat_request(prompt: str, chat_id: str, user_id: str) -> str:
    """Mock implementation of POST /v1/chat/submit"""
    request_id = str(uuid.uuid4())
    
    want_chart = any(k in prompt.lower() for k in ["trend", "趨勢", "圖", "chart", "sales"])
    want_map   = any(k in prompt.lower() for k in ["map", "地圖", "分佈", "distribution"])
    want_rag   = any(k in prompt.lower() for k in ["policy", "document", "規定", "文件", "rag", "search"])
    
    task_type = "general"
    if want_chart: task_type = "chart"
    elif want_map: task_type = "map"
    elif want_rag: task_type = "rag"
    
    _CHAT_TASKS[request_id] = {
        "status": "pending",
        "step_index": 0,
        "type": task_type,
        "prompt": prompt,
        "created_at": time.time(),
        "steps": [], # Will hold the status sequence
        "final_result": None
    }
    
    # Setup the sequence of status messages the frontend will poll
    if task_type == "chart":
        _CHAT_TASKS[request_id]["steps"] = [
            ("🧠", "Understanding your question...", 0.3),
            ("🔧", "Translating to Data API query...", 0.4),
            ("🗄️", "Fetching data from Cache/DB [POST /v1/data/fetch]...", 0.8),
            ("🎨", "Rendering Stateless Chart [POST /v1/charts/generate]...", 0.2),
            ("🧠", "Requesting Chart Insight [Caching enabled]...", 0.5)
        ]
    elif task_type == "map":
         _CHAT_TASKS[request_id]["steps"] = [
            ("🧠", "Understanding location intent...", 0.3),
            ("🔧", "Translating to Data API query...", 0.4),
            ("🗄️", "Fetching data from Cache/DB [POST /v1/data/fetch]...", 0.8),
            ("🎨", "Rendering Stateless Map [POST /v1/charts/generate]...", 0.2),
            ("🧠", "Requesting Map Insight [Caching enabled]...", 0.5)
        ]
    elif task_type == "rag":
         _CHAT_TASKS[request_id]["steps"] = [
            ("🧠", "Analyzing query for search intent...", 0.4),
            ("🗄️", "Embedding query and searching Vector DB...", 1.2),
            ("📄", "Retrieving relevant document chunks...", 0.3),
            ("🧠", "Synthesizing answer from sources...", 1.5)
        ]
    else:
         _CHAT_TASKS[request_id]["steps"] = [
            ("🧠", "Searching knowledge base...", 0.5),
            ("🤖", "Routing to general-answer sub-agent", 0.6),
        ]
         
    return request_id

def poll_chat_status(request_id: str) -> Dict[str, Any]:
    """Mock implementation of GET /v1/chat/status/{request_id}"""
    if request_id not in _CHAT_TASKS:
        return {"status": "error", "message": "Invalid request ID"}
        
    task = _CHAT_TASKS[request_id]
    
    if task["status"] == "complete":
         return {"status": "complete", "message": "Done"}
         
    # Progress the task
    idx = task["step_index"]
    if idx < len(task["steps"]):
        # Simulate time passing (in a real app, this is async)
        step_icon, step_msg, step_delay = task["steps"][idx]
        time.sleep(step_delay) # Block slightly to simulate work
        task["step_index"] += 1
        
        # If we just finished the last step, mark complete and generate result
        if task["step_index"] >= len(task["steps"]):
            task["status"] = "complete"
            _generate_final_result(request_id)
            
        return {"status": "processing", "message": f"{step_icon} {step_msg}"}
        
    return {"status": "complete", "message": "Done"}

def get_chat_result(request_id: str) -> Dict[str, Any]:
    """Mock implementation of GET /v1/chat/result/{request_id}"""
    if request_id not in _CHAT_TASKS:
        return {"error": "Invalid request ID"}
    
    task = _CHAT_TASKS[request_id]
    if task["status"] != "complete":
        return {"error": "Task not complete yet"}
        
    return task["final_result"]


def _generate_final_result(request_id: str):
    """Internal helper to build the final block response when task completes."""
    task = _CHAT_TASKS[request_id]
    t_type = task["type"]
    prompt = task["prompt"]
    
    blocks = []
    trace = []
    
    if t_type == "chart":
        blocks.append({"type": "text", "content": f"Here is the product trend analysis for your query: *'{prompt}'*"})
        
        # 1. Fetch Data
        df = fetch_data(
            raw_data_source="sales_table",
            columns=["Date", "Product A", "Product B", "Product C"]
        )
        
        # 2. Render Chart Statelessly
        chart_res = generate_universal_chart(
             chart_type="line",
             data=df,
             config={"title": "📈 30-Day Sales Trend", "x": "Date", "y": ["Product A", "Product B", "Product C"]}
        )
        
        # 3. Get Cached Insight (using memory id or hash of df for mock)
        insight_key = f"sales_insight_{id(df)}" if df is not _DATA_CACHE.get("sales_table|Date-Product A-Product B-Product C|None|None|None") else "sales_insight_cached"
        insight = generate_chart_insight(insight_key, "line")
        
        blocks.append({
            "type": "plotly",
            "spec": chart_res["spec"],
            "insight": insight
        })
        blocks.append({"type": "text", "content": "Notice how fast it loads if you ask again (Data & Insight Cache Hit)!"})
        
        trace = [
            {"type": "llm_call",  "label": "Intent detection", "duration_ms": 310},
            {"type": "tool_call", "label": "fetch_data()", "duration_ms": 850, "detail": "Called POST /v1/data/fetch"},
            {"type": "tool_call", "label": "generate_universal_chart()", "duration_ms": 120, "detail": "Stateless rendering"},
            {"type": "llm_call",  "label": "generate_chart_insight()", "duration_ms": 940, "detail": "Insight Generation (Cached)"},
        ]
        
    elif t_type == "map":
        blocks.append({"type": "text", "content": f"Here is the user geographic distribution for: *'{prompt}'*"})
        
        # 1. Fetch Data
        df = fetch_data(
            raw_data_source="user_geo_table",
            columns=["lat", "lon"]
        )
        
        # 2. Render Chart Statelessly
        chart_res = generate_universal_chart(
             chart_type="map",
             data=df,
             config={"title": "🗺️ User Geographic Distribution", "lat": "lat", "lon": "lon"}
        )
        
        # 3. Get Cached Insight
        insight_key = f"geo_insight_{id(df)}" if df is not _DATA_CACHE.get("user_geo_table|lat-lon|None|None|None") else "geo_insight_cached"
        insight = generate_chart_insight(insight_key, "map")
        
        blocks.append({
            "type": "plotly",
            "spec": chart_res["spec"],
            "insight": insight
        })
        
        trace = [
            {"type": "llm_call",  "label": "Intent detection", "duration_ms": 295},
            {"type": "tool_call", "label": "fetch_data()", "duration_ms": 750, "detail": "Called POST /v1/data/fetch"},
            {"type": "tool_call", "label": "generate_universal_chart()", "duration_ms": 100, "detail": "Stateless rendering"},
            {"type": "llm_call",  "label": "generate_chart_insight()", "duration_ms": 810, "detail": "Insight Generation (Cached)"},
        ]
        
    elif t_type == "rag":
        blocks.append({"type": "text", "content": f"Based on the internal knowledge base, here is the information regarding: *'{prompt}'*"})
        blocks.append({"type": "text", "content": "According to the **2025 Employee Handbook** and the **Remote Work Policy**, employees are allowed up to 3 days of remote work per week with manager approval. Core hours are 10 AM to 3 PM."})
        
        # New Reference Block
        blocks.append({
            "type": "reference",
            "sources": [
                {
                    "title": "2025 Employee Handbook (v2.1)", 
                    "url": "https://wiki.example.com/handbook", 
                    "snippet": "...core hours for all employees are 10:00 AM to 3:00 PM local time..."
                },
                {
                    "title": "Remote Work Policy", 
                    "url": "https://wiki.example.com/remote-policy", 
                    "snippet": "...up to 3 days of remote work per week may be granted subject to manager approval..."
                }
            ]
        })
        
        trace = [
            {"type": "llm_call",  "label": "Intent detection (RAG)", "duration_ms": 210},
            {"type": "tool_call", "label": "vector_search()", "duration_ms": 1150, "detail": "Found 2 relevant chunks"},
            {"type": "llm_call",  "label": "Answer Synthesis", "duration_ms": 1850, "detail": "Generated using retrieved context"}
        ]
        
    else:
         blocks = [
            {"type": "text", "content": f"I received your message: *'{prompt}'*."},
            {"type": "text", "content": "Try asking about **product trends** or **user distribution map** to see the caching API in action."},
        ]
         trace = [
            {"type": "llm_call",  "label": "Intent detection", "duration_ms": 280},
            {"type": "sub_agent", "label": "General-answer sub-agent", "duration_ms": 610},
        ]
        
    task["final_result"] = {"blocks": blocks, "trace": trace}
