# Week 2 Demo Flow — AssetMind AI

This walkthrough guides you through demonstrating the live Week 2 features of AssetMind AI (Asset Intelligence, Knowledge Graph, and RAG Scoping).

## Prerequisites

1. Ensure the PostgreSQL container is running:
   ```bash
   docker-compose up -d db
   ```
2. Start the FastAPI backend:
   ```bash
   cd apps/api
   export PERSISTENCE_BACKEND=postgres
   export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind
   .venv/bin/python -m app.main
   ```
3. Start the Next.js frontend:
   ```bash
   cd apps/web
   npm run dev
   ```

---

## Step-by-Step Demo Flow

### Step 1: Live Dashboard Overview (`/`)
* **Show:** Live KPI counts (e.g. 7 Assets, 9 Knowledge Edges).
* **Highlight:** The **Risk Summary** table showing prioritized risk scores (e.g. `P-101` at High Risk with 6.2 mm/s vibration).
* **Explain:** These stats are fetched live from `GET /dashboard/summary` backed by SQL queries in Postgres.

### Step 2: Upload CSV / Excel Datasets (`/upload`)
* **Show:** The file upload box accepting `.pdf`, `.txt`, `.csv`, and `.xlsx`.
* **Action:** Select and upload a sample file (e.g., `work_orders_clean.csv` or a manual).
* **Highlight:** The post-upload summary listing **Document Created**, **Chunks Created**, **Assets Extracted**, and **Facts Extracted** in real-time.

### Step 3: Browse Scored Assets (`/assets`)
* **Show:** The asset list page.
* **Highlight:** Cards showing risk levels, matching counts, and reasons (e.g. "Overdue item or compliance gap").

### Step 4: Asset Details & Interactive Graph (`/assets/{tag}`)
* **Show:** Click on `V-101` or `P-101`.
* **Tabs to present:**
  * **Overview:** Displays details and a preview card of recent timeline events.
  * **Timeline:** Shows chronological maintenance and audit events with source links.
  * **Knowledge Graph:**
    * Show the interactive radial SVG layout.
    * Click a node to open the **Node Inspector** sidebar. Show how it displays raw text from chunk nodes.
    * Filter out chunks or query relation types to demonstrate real-time graph rendering.
  * **Facts:** Displays a table of all entities extracted from documents.
  * **Ask:** Submit a localized query (e.g. *"What checks are required?"*) scoped specifically to this asset.

### Step 5: Operations Copilot & Scoped RAG (`/copilot`)
* **Show:** Navigate to the Copilot page.
* **Scoping:** Choose `P-101` from the **Scope by Asset** dropdown.
* **Ask:** *"What is the maximum allowable vibration?"*
* **Highlight:**
  * The **Query Intent** badge classified as `equipment_spec`.
  * The **Page Numbers** next to citations.
  * The **Related Assets** badges linking to other equipment tags.
  * Click a citation filename and demonstrate jumping straight to the document's chunk inspector.

### Step 6: RAG Evaluation Dashboard (`/evaluation`)
* **Show:** The RAG Evaluation tab from the sidebar.
* **Highlight:** Global Top-1/Top-3 hit rates and average latency.
* **Interactive Run Inspector:** Click on a question row to show the exact grounding chunks, expected answer, and actual output comparison.
