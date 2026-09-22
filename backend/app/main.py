"""Backend for the APS Citation Explorer: FastAPI + SQLite.

Remembers which papers the user has hidden from the viewer, plus a copy of the sample's paper metadata.
Run from the repo root:  uvicorn backend.app.main:app --reload --port 8000
"""
import json
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException

ROOT = Path(__file__).resolve().parents[2]
GRAPH_JSON = Path(os.environ.get("GRAPH_JSON", ROOT / "frontend" / "public" / "data" / "graph.json"))
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "backend" / "data" / "aps.db"))

SCHEMA = """
DROP TABLE IF EXISTS annotation_tags;         -- tables from an earlier tags-and-notes version
DROP TABLE IF EXISTS annotations;
CREATE TABLE IF NOT EXISTS papers (           -- dataset metadata, seeded from graph.json
    doi        TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    discipline TEXT,
    journal    TEXT,
    year       INTEGER,
    cited      INTEGER
);
CREATE TABLE IF NOT EXISTS hidden_papers (    -- papers the user has hidden from the viewer
    doi       TEXT PRIMARY KEY REFERENCES papers(doi) ON DELETE CASCADE,
    hidden_at TEXT NOT NULL
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed_papers(conn):
    """Fill the papers table from graph.json (safe to repeat on every start)."""
    if not GRAPH_JSON.exists():
        print(f"warning: {GRAPH_JSON} not found; papers table left empty")
        return
    nodes = json.loads(GRAPH_JSON.read_text())["nodes"]
    conn.executemany(
        # An upsert, not INSERT OR REPLACE: replacing a row would cascade-delete its hidden flag.
        "INSERT INTO papers (doi, title, discipline, journal, year, cited) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(doi) DO UPDATE SET title = excluded.title, discipline = excluded.discipline, "
        "journal = excluded.journal, year = excluded.year, cited = excluded.cited",
        [(n["doi"], n["title"], n["discipline"], n["abbr"], int(n["date"][:4]), n["cited"]) for n in nodes],
    )
    conn.commit()


@asynccontextmanager
async def lifespan(app):
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        seed_papers(conn)
    yield


app = FastAPI(title="APS Citation Explorer API", lifespan=lifespan)


def get_db():
    with closing(connect()) as conn:
        yield conn


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def stats(db: sqlite3.Connection = Depends(get_db)):
    return {
        "papers": db.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
        "hidden": db.execute("SELECT COUNT(*) FROM hidden_papers").fetchone()[0],
    }


@app.get("/api/hidden")
def list_hidden(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT doi, hidden_at FROM hidden_papers ORDER BY hidden_at DESC, doi").fetchall()
    return [{"doi": r["doi"], "hidden_at": r["hidden_at"]} for r in rows]


@app.put("/api/hidden/{doi:path}")
def hide_paper(doi: str, db: sqlite3.Connection = Depends(get_db)):
    """Hide a paper (idempotent)."""
    if db.execute("SELECT 1 FROM papers WHERE doi = ?", (doi,)).fetchone() is None:
        raise HTTPException(404, f"Unknown paper: {doi}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute("INSERT INTO hidden_papers (doi, hidden_at) VALUES (?, ?) ON CONFLICT(doi) DO NOTHING", (doi, now))
    db.commit()
    return {"doi": doi, "hidden": True}


@app.delete("/api/hidden/{doi:path}", status_code=204)
def restore_paper(doi: str, db: sqlite3.Connection = Depends(get_db)):
    """Un-hide one paper."""
    db.execute("DELETE FROM hidden_papers WHERE doi = ?", (doi,))
    db.commit()


@app.delete("/api/hidden", status_code=204)
def restore_all(db: sqlite3.Connection = Depends(get_db)):
    """Un-hide every paper."""
    db.execute("DELETE FROM hidden_papers")
    db.commit()
