# X-chat 應用程式架構與 API 實作指南

## 1. 應用程式架構設計

前端應用程式 (`app.py`) 是使用 **Streamlit** 建構的，並且設計為雙模式介面，結合了傳統的商業智慧 (BI) 功能與互動式 AI 聊天機器人。

### 1.1 核心元件
* **雙模式系統**：
  * **一般模式 (Dashboard)**：傳統的選單驅動視圖，包含「儀表板 (Dashboard)」、「系統介紹 (Introduction)」與「專案時程 (Schedule)」。顯示預先定義的 KPI 指標、圖表與交易紀錄。
  * **AI 助理模式 (AI Mode)**：由 LLM 驅動的對話介面，允許使用者以自然語言提問，並接收包含多種格式的區塊式回應（純文字、Plotly 圖表、地圖、數據指標）。
* **狀態管理 (State Management)**：大量使用 `st.session_state` 來追蹤：
  * `authentication_status`, `name`, `username`：用於使用者登入驗證狀態。
  * `chat_history`, `current_chat`：用於在頁面重新載入時保存 AI 聊天紀錄。
  * `normal_view`：用於紀錄在一般模式下目前停留在哪一個頁面。
  * `close_sidebar_flag`：用於程式化控制 UI。
* **權限認證 (Authentication)**：透過 `streamlit-authenticator` 處理。設定檔會先檢查 Streamlit Secrets (`st.secrets`，適用於正式機部署)，如果沒有則退回使用本地端的 `auth_config.yaml`。如果是首次執行且找不到設定檔，則會自動初始化預設設定。
* **客製化 UI 調整**： 
  * 注入客製化 CSS 以隱藏 Streamlit 預設的頂部選單與底部資訊。
  * 利用沙盒化的 HTML/Javascript 注入技術 (`st.components.v1.html`) 來透過程式自動收合側邊欄，讓使用者在切換視圖時有更流暢的體驗。

---

## 2. 後端 API 需求規格

目前的實作包含多個標記為 `TODO [BACKEND API]` 的佔位函式。未來需要將這些部分串接到真實的後端微服務。

### 2.1 一般模式 (Dashboard) API
儀表板需要能獲取即時指標與歷史時間序列的端點，以及由 AI 洞察分析所產生的情境文字。
* **KPI 關鍵指標 (Metrics)**
  * **輸入**：使用者或組織 ID，時間範圍。
  * **輸出**：總使用者數、活躍連線數、營收的絕對數值與變動百分比 (Delta)。
  * *附加回傳*：一段總結上述指標狀況的 AI 洞察文字。
* **資料獲取 API (Data Fetch API - 資料處理與快取層)**
  * **目的**：負責向資料庫獲取、過濾、聚合並**快取**原始資料。LLM 可以透過此 API 有效率地拉取特定維度的資料切片。**快取機制實作於此層**：如果底層資料庫尚未更新，且請求了一模一樣的查詢參數，則直接回傳快取在記憶體中的 DataFrame。
  * **端點**：`POST /v1/data/fetch`
  * **輸入**：
    * `raw_data_source`：原始資料來源的參照 (例如：`sales_table`, `user_geo_table`)。
    * `columns`：需要取出的欄位清單。
    * `filters`：過濾條件陣列 (例如：`[{"column": "region", "operator": "==", "value": "North"}]`)。
    * `groupby`：負責 Group By 的欄位陣列 (例如：`["Date", "Product"]`)。
    * `aggregation`：聚合指標 (例如：`{"revenue": "sum", "users": "count"}`)。
    * `limit` / `offset`：用於分頁。
  * **輸出**：處理後的 JSON 陣列紀錄資料。

* **萬用圖表生成 API (Universal Chart Generation API - 無狀態渲染層)**
  * **目的**：單一且整合的圖表渲染 API。此 API **不負責**向資料庫撈取資料，也不做資料快取。它單純接收來自 LLM (或前端) 的實際資料集與繪圖設定，並回傳渲染視覺圖表的指令。
  * **端點**：`POST /v1/charts/generate`
  * **輸入**： 
    * `chart_type`：要繪製的圖表類型 (例如：`line`, `bar`, `scatter`, `map`)。
    * `data`：要畫在圖上的實際資料酬載 (通常是從 **Data Fetch API** 取得的回傳值)。
    * `config`：圖表設定檔 (例如：`{"x": "Date", "y": "revenue", "color": "Product"}`)。
  * **輸出**：Streamlit 可以使用 `st.plotly_chart()` 直接無縫渲染的 **Plotly JSON 規格** (與 AI Mode 中的 `plotly` block 格式完全一致)。
  * *附加回傳*：一段解釋圖表意義的可選 AI 洞察分析文字 (Insights 另有 API 可以產生並快取)。

  **資料獲取 & 圖表生成流程圖 (Flowchart)：**
  ```mermaid
  flowchart TD
      A[LLM 代理人請求資料: POST /v1/data/fetch] --> B{有命中快取 (Cache Hit)?}
      B -- 是 --> C{原始資料有更新嗎?}
      B -- 否 --> D[從資料庫撈取原始資料]
      C -- 是 --> D
      C -- 否 --> E[回傳快取中已處理好之資料]
      D --> F[套用過濾過濾 (Filters)、分組 (GroupBy)、聚合 (Aggr)]
      F --> G[更新快取]
      G --> E
      
      E --> H[LLM 決定圖表類型與配置細節]
      H --> I[LLM 請求畫圖: POST /v1/charts/generate]
      I --> J[產生 AI 洞察文字]
      J --> K[回傳 Plotly JSON 規格]
  ```

* **交易紀錄分頁表 (Transactions Log)**
  * **輸入**：分頁參數 (limit, offset/page)，過濾條件 (status)。
  * **輸出**：近期的交易物件陣列 (Date, Amount, Status)。
  * *附加回傳*：AI 洞察分析，特別標註異常值或錯誤率。

### 2.2 AI 聊天模式 (Chat Mode) API
聊天介面使用了真實的非同步請求與輪詢 (Polling) 機制，並相容於 `api_response_spec.md`。

**AI 聊天模式輪詢流程圖 (Polling Flowchart)：**
```mermaid
flowchart TD
    A[使用者送出問題] --> B[POST /v1/chat/submit]
    B --> C[收到任務 ID (request_id)]
    C --> D[GET /v1/chat/status/request_id]
    D --> E{擷取狀態 == complete?}
    E -- 否 --> F[將目前進度更新至前端 UI 狀態列，並等待]
    F --> D
    E -- 是 --> G[GET /v1/chat/result/request_id]
    G --> H[渲染推理軌跡 (Trace) 與區塊 (Blocks) UI]
```

* **1. 提交聊天請求 (Submit Chat Request)**
  * **端點**：`POST /v1/chat/submit`
  * **輸入**：使用者提問 (User Prompt), `chat_id`, 使用者語境/歷史訊息。
  * **輸出**：`request_id` (任務追蹤 ID)。
* **2. 輪詢查詢狀態 (Poll for Status)**
  * **端點**：`GET /v1/chat/status/{request_id}`
  * **輸入**：`request_id`。
  * **輸出**：目前的執行進度/狀態字串 (例如："Analysing request...", "Calling tools...")。Streamlit 會使用這段字串即時更新 UI 上的 `st.status` 狀態框。
* **3. 獲取最終分析結果 (Fetch Final Result)**
  * **端點**：`GET /v1/chat/result/{request_id}`
  * **輸入**：`request_id`。
  * **輸出**：符合 `api_response_spec.md` 規範的標準化 JSON。
    * `blocks`：多種內容格式的陣列區塊 (`text`, `plotly`, `map`, `metric`)。
    * `trace`：內部執行步驟列表 (`llm_call`, `tool_call`, `sub_agent`, `query`)，提供推理展開列表 (Reasoning Expander) 顯示給使用者看邏輯軌跡。

### 2.3 平台通用 API

* **遙測與審計紀錄 API (Telemetry & Audit API)**
  * **目的**：為了總結報告、計費監控與系統優化，架構上**不建議**讓 LLM 或前端各自處理日誌。應該建立一個獨立且非同步的遙測 API，在 `POST /v1/chat/result` (回傳給前端之前) 或 `POST /v1/data/fetch` 等核心節點，由**後端自動攔截並發送**紀錄。這能確保所有指標被統一且完整地收集，不會因為前端斷線或 LLM 生產失敗而遺失紀錄。
  * **端點**：`POST /v1/telemetry/log` (通常由內部微服務呼叫，或前端事件觸發)
  * **輸入結構** (Event Payload)：
    ```json
    {
      "event_type": "string (e.g., 'llm_call', 'chart_generated', 'user_query')",
      "user_id": "string",
      "session_id": "string",
      "timestamp": "ISO-8601 string",
      "metrics": {
          "tokens_used": "integer (optional)",
          "latency_ms": "integer",
          "cache_hit": "boolean"
      },
      "metadata": {
          "query_text": "string (optional)",
          "chart_type": "string (optional)",
          "model_version": "string (optional)"
      }
    }
    ```
  * **說明**：
    * `llm_call` 事件：紀錄呼叫次數、花費的 Token 以及回應時間。
    * `chart_generated` 事件：紀錄哪種圖表最常被畫、所使用的資料表 (`raw_data_source`) 是什麼，以及快取命中率。
    * `user_query` 事件：原始紀錄大家問了什麼問題，後續可以用來做「最熱門提問」統整報告，或是改善 LLM 系統提示。

* **使用者意見回饋收集 (Feedback Collection)**
  * **端點**：`POST /v1/feedback`
  * **輸入**： 
    ```json
    {
      "user_id": "string",
      "rating": "integer (1-5)",
      "message": "string (optional)",
      "timestamp": "ISO-8601 string",
      "context": "string (e.g., 'ai_mode' or 'normal_mode')"
    }
    ```
  * **輸出**：成功確認回應 (200 OK)。
