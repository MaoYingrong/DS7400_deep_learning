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

Requirements: Node.js 20+ and npm. The sample data (`frontend/public/data/graph.json`) is committed, so nothing else is needed.

```bash
cd frontend
npm install
npm run dev        # then open the printed URL, normally http://localhost:5173
```

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

## Major libraries and frameworks

React 19, Vite 6, [deck.gl](https://deck.gl) 9 (WebGL rendering). Data pipeline: Python, pandas, SciPy, scikit-learn, UMAP.

## Project layout

```
frontend/src/App.jsx                 state: selection, filters, search
frontend/src/components/GraphMap.jsx the deck.gl map
frontend/src/components/Sidebar.jsx  search, filters, legend
frontend/src/components/DetailPanel.jsx  selected-paper details
frontend/src/data.js                 loads graph.json, builds cites / cited-by lookups
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

- Interactive annotation: **not implemented yet**
- Backend / database: **not implemented yet**

## Notes

The APS dataset comes from the APS Data Sets for Research programme; the sample here is a small subset for coursework.
