# Hackathon Presentation Script — AssetMind AI

Use this script to deliver a high-impact, 3-minute presentation of AssetMind AI to the hackathon judges.

---

## 🎤 Minute 0:00 - 0:45 ─ The Hook & The Problem
> **Presenter:** *"Judges, in heavy industrial plants like oil refineries and chemical plants, operators are drowning in data. When an alarm goes off on a pump, finding the right procedure requires sorting through thousands of pages of PDF manuals, Excel sheets, and handwritten work orders.*
>
> *AssetMind AI solves this. We upgrade traditional text search into an **Asset-Scoped Knowledge Graph** and **Grounded RAG Copilot** that gives operators instant, trusted answers with complete traceability."*

---

## 🎤 Minute 0:45 - 1:45 ─ Live UI Demonstration
* (Navigate to Dashboard page)
> **Presenter:** *"Here is our live dashboard. We ingest raw PDFs, Excel sheets, and CSV work orders, automatically parse them, and extract **industrial facts** like equipment tags, failure modes, and compliance deadlines.*
>
> *Instead of simple search, we score assets dynamically. For example, Pump P-101 has a **High Risk** score because of a 6.2 mm/s vibration spike logged in an inspection report."*

* (Click on Pump P-101 details and go to Knowledge Graph tab)
> **Presenter:** *"Clicking on P-101, we see its entire operational context. Our **interactive Knowledge Graph** maps connections between this pump, the manuals that mention it, and the compliance certificates it depends on.*
>
> *Operators can click on any node to inspect evidence text or jump directly to the source document details."*

---

## 🎤 Minute 1:45 - 2:30 ─ Grounded RAG & Scoping
* (Navigate to Copilot page, select P-101 scope)
> **Presenter:** *"Now, let's look at the Copilot. If we ask about P-101's vibration threshold, AssetMind AI does two unique things: first, it classifies the question's intent as an `equipment_spec` to prioritize OEM manuals over noise. Second, it biases the search specifically to P-101's context.*
>
> *The result is a precise answer citing exact page numbers. Best of all, every citation is a clickable link leading straight back to the original source text."*

---

## 🎤 Minute 2:30 - 3:00 ─ Ground Truth Evaluation & Close
* (Navigate to Evaluation dashboard)
> **Presenter:** *"But how do we prove this works? Under the hood, we built a fully automated RAG Evaluation Suite. We measure Top-1 and Top-3 source hit rates, asset tagging correctness, and latency against a standard industrial benchmark.*
>
> *With an **83.3% Top-1 hit rate** and **248ms latency**, AssetMind AI provides the speed and trust heavy industries need.*
>
> *Thank you, we are now open for your questions!"*
