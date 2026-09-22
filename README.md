# APS Citation Explorer

DS7400 Deep Learning – Homework 1: a web-based data viewer that will become the home for deep-learning models in later homeworks.
The current application supports data exploration and persistent hide/restore choices; deep-learning models are not yet implemented.

## What it is

An interactive map of physics papers. Each **paper is a node**; **citations are edges**. The viewer works on a
2,000-paper sample of the [APS (American Physical Society) dataset](https://journals.aps.org/datasets) – papers published in
Physical Review journals between 2016 and 2022 – with the 20,381 citations between them.

## Type of data

**Graph / network data** (a citation network). Per paper: title, authors, affiliations, journal, date, DOI, article type,
PhySH topic classification (disciplines + concepts), and citation links.

Citation edges point from the citing paper to the cited paper. The displayed links connect only papers in the sample;
the citation counts used for dot sizes and filtering count incoming citations from the broader 2016–2022 APS paper set.
They are not worldwide citation totals. The sample spans 19 disciplines and favors well-connected papers, so it is intended
for exploration rather than as an unbiased representation of all APS research.

## Running the application

Requirements: Node.js 20+, npm, and Python 3.10+. The sample data (`frontend/public/data/graph.json`) is committed.
Run the backend and the frontend in **two terminals**, both from the repo root.

**Terminal 1 – backend (FastAPI + SQLite):**

```bash
python3 -m venv .venv
source .venv/bin/activate                   # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --port 8000  # creates backend/data/aps.db on first start
```

**Terminal 2 – frontend:**

```bash
cd frontend
npm install
npm run dev        # then open the printed URL, normally http://localhost:5173
```

The header shows **Backend connected** once the two are talking. Without the backend the viewer still works, but hiding papers is disabled.
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
- **Interactive annotation: hide papers you don't want to see** – select a paper and click **Hide this paper** in the detail panel.
  It disappears from the map (with its citation lines), from search, and from the References / Cited by lists. A toast offers **Undo**,
  and everything you've hidden is listed under **Hidden papers** in the sidebar with **Restore** / **Restore all** buttons.
  It is a user-curated mark on individual nodes, stored in the database, so it persists across reloads and restarts.
  Hiding never deletes a paper's metadata or citation data; restoring removes only its hidden status.
- **Backend / database** – a FastAPI + SQLite service stores which papers are hidden (plus the sample's paper metadata).

## Major libraries and frameworks

React 19, Vite 6, [deck.gl](https://deck.gl) 9 (WebGL rendering). Backend: FastAPI, SQLite (Docker optional). Data pipeline: Python, pandas, SciPy, scikit-learn, UMAP.

## Project layout

```
frontend/src/App.jsx                 state: selection, filters, search
frontend/src/components/GraphMap.jsx the deck.gl map
frontend/src/components/Sidebar.jsx  search, filters, legend
frontend/src/components/DetailPanel.jsx  selected-paper details
frontend/src/data.js                 loads graph.json, builds cites / cited-by lookups
frontend/src/api.js                  calls to the backend API
backend/app/main.py                  FastAPI app + SQLite schema
backend/Dockerfile, docker-compose.yml   optional Docker setup for the backend
frontend/public/data/graph.json      the sample dataset (generated)
pipeline/build_data.py               builds graph.json from the raw APS files
01_explore_aps_dataset.ipynb          initial exploration of raw citations and metadata
```

The frontend loads `graph.json` directly and builds reference/cited-by lookups in the browser. Vite forwards `/api`
requests to FastAPI on port 8000; the backend seeds paper metadata into SQLite and saves hide/restore choices.
The exploration notebook uses an original cluster-specific `BASE_DIR`; update that path to your local APS folder before running it.

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

- Interactive annotation: **implemented as a hidden/visible status on individual graph nodes**, with hide, undo, and restore controls.
  Free-text notes, custom tags, and an “Important” label are not implemented in the current version.
- Backend / database: **implemented** (FastAPI + SQLite).

### Backend API

| Method & path | Purpose |
|---|---|
| `GET /api/stats` | number of papers and of hidden papers |
| `GET /api/hidden` | DOIs and timestamps of all hidden papers |
| `PUT /api/hidden/{doi}` | hide a paper (safe to repeat) |
| `DELETE /api/hidden/{doi}` | restore one paper |
| `DELETE /api/hidden` | restore all papers |

SQLite tables: `papers` (metadata for the 2,000 sampled papers, seeded from `graph.json` at startup) and `hidden_papers`
(DOI + time hidden). Hiding inserts a row into `hidden_papers` and leaves the `papers` row and source graph unchanged.
Restoring deletes only the corresponding `hidden_papers` row. Hidden status is keyed by DOI rather than sample index,
so it can be retained for the same paper when the sample is rebuilt. These choices are shared by clients using the same backend;
there are no separate user accounts. The database file
`backend/data/aps.db` is git-ignored. Interactive API docs are at http://localhost:8000/docs while the backend runs.

### Demonstrating persistence

With both services running, select a paper, click **Hide this paper**, and reload the page. The paper remains in the
**Hidden papers** list. Click **Restore** to bring it back, or **Restore all** to clear all hidden statuses.

For the local Python backend, the following read-only queries can demonstrate the stored status and preserved metadata
from the repository root (requires the SQLite command-line tool):

```bash
sqlite3 backend/data/aps.db "SELECT doi, hidden_at FROM hidden_papers LIMIT 5;"
sqlite3 backend/data/aps.db "SELECT p.doi, p.title FROM papers p JOIN hidden_papers h ON p.doi = h.doi LIMIT 5;"
```

The Docker setup stores its database in the `aps-data` volume instead of this local path.

## Planned deep-learning extensions

HW1 establishes the viewer; the following are proposed extensions for later assignments, not current features.

| Task | Possible model and training data | Viewer integration |
|---|---|---|
| Research-field prediction (node classification) | A graph neural network using citation connections and title features to predict existing PhySH discipline labels. Target discipline labels would be excluded from input features. | Show predicted fields and confidence alongside recorded fields. |
| Related-paper recommendations | A neural encoder that learns paper embeddings from titles and citation neighborhoods. | Add a ranked “Related papers” panel, including papers without a direct citation link. |
| Citation link prediction | A graph neural network with a pairwise decoder, evaluated on held-out citation edges and non-edge pairs. | Show suggested citation connections separately from observed links. |

Field prediction is the intended first step. Training can use a larger subset of the raw APS data while the viewer
continues to display a manageable sample. Evaluation should use held-out labels or edges and compare against simple
baselines. The existing UMAP map is a dimensionality-reduction visualization, not an implemented deep-learning model.



## Notes

The APS dataset comes from the APS Data Sets for Research programme; the sample here is a small subset for coursework.
