# APS Citation Explorer

DS7400 Deep Learning – Homework 1: a web-based data viewer that will become the home for deep-learning models in later homeworks.

## What it is

An interactive map of physics papers. Each **paper is a node**; **citations are edges**. The viewer works on a
2,000-paper sample of the [APS (American Physical Society) dataset](https://journals.aps.org/datasets) – papers published in
Physical Review journals between 2016 and 2022 – with the 20,381 citations between them.

## Type of data

**Graph / network data** (a citation network). Per paper: title, authors, affiliations, journal, date, DOI, article type,
PhySH topic classification (disciplines + concepts), and citation links.

## Running the application

Requirements: Node.js 20+, npm, and Python 3.10+. The sample data (`frontend/public/data/graph.json`) is committed.
Run the backend and the frontend in **two terminals**, both from the repo root.

**Terminal 1 – backend (FastAPI + SQLite):**
```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --port 8000      # creates backend/data/aps.db on first start
```

**Terminal 2 – frontend:**
```bash
cd frontend
npm install
npm run dev        # then open the printed URL, normally http://localhost:5173
```

The header shows **Backend connected** once the two are talking. Without the backend the viewer still works, but annotations are disabled.
Instead of `pip`/`uvicorn`, the backend can also run in Docker: `docker compose up --build` (not tested on the author's machine, where Docker isn't installed).

## Features

- **Map view** – all papers as dots on a 2-D map (WebGL, via deck.gl). Drag to pan, scroll to zoom, *Reset view* to refit.
  Nearby dots have similar PhySH topics and citation neighbours; color = discipline; size = number of citations received.
- **Hover** a dot for a tooltip (title, authors, journal/year, citation count, discipline).
- **Click** a dot to select it: its references (black) and citing papers (red) are drawn, unrelated papers fade out, and the
  detail panel shows authors, affiliations, DOI link, journal details, PhySH topics, and clickable lists of
  *References* and *Cited by* to hop through the citation network.
- **Search** by title words, author name or DOI; picking a result flies to that paper.
- **Filters** – journal, year range, minimum citations, and per-discipline toggles (the legend doubles as the filter).
  Optionally draw all 20K citation links.
- **Interactive annotation** – select a paper and use the *My annotation* box in the detail panel:
  click preset tags (Important, To read, Relevant to my research, Method, Question), add your own tags, and write a free-text note.
  It saves automatically. Annotated papers get a **★ marker on the map**, are listed under *My annotations* in the sidebar, and can
  be filtered by tag ("Annotated only" / "Tagged …"). *Export annotations (CSV)* downloads them (DOI, title, tags, note).
- **Backend / database** – a FastAPI + SQLite service stores annotations so they persist across reloads and restarts.

## Major libraries and frameworks

React 19, Vite 6, [deck.gl](https://deck.gl) 9 (WebGL rendering). Backend: FastAPI, SQLite (Docker optional). Data pipeline: Python, pandas, SciPy, scikit-learn, UMAP.

## Project layout

```
frontend/src/App.jsx                 state: selection, filters, search
frontend/src/components/GraphMap.jsx the deck.gl map
frontend/src/components/Sidebar.jsx  search, filters, legend
frontend/src/components/DetailPanel.jsx  selected-paper details
frontend/src/components/AnnotationEditor.jsx  tags + note editor
frontend/src/data.js                 loads graph.json, builds cites / cited-by lookups
frontend/src/api.js                  calls to the backend API
backend/app/main.py                  FastAPI app + SQLite schema
backend/Dockerfile, docker-compose.yml   optional Docker setup for the backend
frontend/public/data/graph.json      the sample dataset (generated)
pipeline/build_data.py               builds graph.json from the raw APS files
```

## Regenerating the sample (optional)

The full raw dataset (~720K papers, 9.8M citations) is **not** in this repo. To rebuild the sample from it:

```bash
pip install -r pipeline/requirements.txt
python pipeline/build_data.py --aps-dir /path/to/APS --n 2000
```

`--aps-dir` must contain `aps-dataset-metadata-2022/` and `aps-dataset-citations-2022.csv`. The script keeps 2016–2022 papers,
draws a sample stratified by discipline (seed papers, then the papers most linked to them, so the sample has visible citation
structure), keeps the citations among sampled papers, and lays the papers out with UMAP over PhySH topics + citation structure.

## Annotation and backend

- Interactive annotation: **implemented** (tags + notes with ★ markers on the map).
- Backend / database: **implemented** (FastAPI + SQLite).

### Backend API

| Method & path | Purpose |
|---|---|
| `GET /api/stats` | paper / annotation counts and tag counts |
| `GET /api/annotations` | all saved annotations |
| `PUT /api/annotations/{doi}` | create or replace `{tags, note}` for a paper (empty tags and note delete it) |
| `DELETE /api/annotations/{doi}` | remove an annotation |
| `GET /api/annotations/export.csv` | download annotations joined with paper metadata |

SQLite tables: `papers` (metadata for the 2,000 sampled papers, seeded from `graph.json` at startup), `annotations` (note per
paper) and `annotation_tags` (tags per paper). Annotations are keyed by DOI, so they stay valid if the sample is rebuilt. The
database file `backend/data/aps.db` is git-ignored. Interactive API docs are at http://localhost:8000/docs while the backend runs.

## Notes

The APS dataset comes from the APS Data Sets for Research programme; the sample here is a small subset for coursework.
