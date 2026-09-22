"""Backend for the APS Citation Explorer: FastAPI + SQLite.

Stores the user's annotations (tags + a note per paper) and a copy of the sample's paper metadata.
Run from the repo root:  uvicorn backend.app.main:app --reload --port 8000
"""
import csv
import io
import json
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]
GRAPH_JSON = Path(os.environ.get("GRAPH_JSON", ROOT / "frontend" / "public" / "data" / "graph.json"))
DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "backend" / "data" / "aps.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (          -- dataset metadata, seeded from graph.json
    doi        TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    discipline TEXT,
    journal    TEXT,
    year       INTEGER,
    cited      INTEGER
);
CREATE TABLE IF NOT EXISTS annotations (     -- one row per annotated paper
    doi        TEXT PRIMARY KEY REFERENCES papers(doi) ON DELETE CASCADE,
    note       TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS annotation_tags ( -- a paper can have many tags
    doi TEXT NOT NULL REFERENCES annotations(doi) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (doi, tag)
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed_papers(conn):
    """Fill the papers table from graph.json the first time (or after the sample is rebuilt)."""
    if not GRAPH_JSON.exists():
        print(f"warning: {GRAPH_JSON} not found; papers table left empty")
        return
    nodes = json.loads(GRAPH_JSON.read_text())["nodes"]
    conn.executemany(
        # An upsert, not INSERT OR REPLACE: replacing a row would cascade-delete its annotations.
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


class AnnotationIn(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field("", max_length=2000)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags):
        out = []
        for t in tags:
            t = " ".join(t.split())
            if len(t) > 40:
                raise ValueError("tags must be at most 40 characters")
            if t and t.lower() not in (x.lower() for x in out):
                out.append(t)
        return out


def read_annotations(conn, doi=None):
    where, args = ("WHERE a.doi = ?", (doi,)) if doi else ("", ())
    rows = conn.execute(f"SELECT a.doi, a.note, a.updated_at FROM annotations a {where} ORDER BY a.updated_at DESC", args).fetchall()
    tags = {}
    for r in conn.execute("SELECT doi, tag FROM annotation_tags ORDER BY tag"):
        tags.setdefault(r["doi"], []).append(r["tag"])
    return [{"doi": r["doi"], "tags": tags.get(r["doi"], []), "note": r["note"], "updated_at": r["updated_at"]} for r in rows]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def stats(db: sqlite3.Connection = Depends(get_db)):
    tag_counts = {r["tag"]: r["n"] for r in db.execute("SELECT tag, COUNT(*) AS n FROM annotation_tags GROUP BY tag ORDER BY n DESC, tag")}
    return {
        "papers": db.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
        "annotations": db.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
        "tags": tag_counts,
    }


@app.get("/api/annotations")
def list_annotations(db: sqlite3.Connection = Depends(get_db)):
    return read_annotations(db)


@app.get("/api/annotations/export.csv")
def export_csv(db: sqlite3.Connection = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["doi", "title", "discipline", "journal", "year", "tags", "note", "updated_at"])
    papers = {r["doi"]: r for r in db.execute("SELECT * FROM papers")}
    for a in read_annotations(db):
        p = papers[a["doi"]]
        w.writerow([a["doi"], p["title"], p["discipline"], p["journal"], p["year"], "; ".join(a["tags"]), a["note"], a["updated_at"]])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="annotations.csv"'})


@app.put("/api/annotations/{doi:path}")
def save_annotation(doi: str, body: AnnotationIn, db: sqlite3.Connection = Depends(get_db)):
    """Create or replace a paper's annotation. Sending no tags and no note removes it."""
    if db.execute("SELECT 1 FROM papers WHERE doi = ?", (doi,)).fetchone() is None:
        raise HTTPException(404, f"Unknown paper: {doi}")
    if not body.tags and not body.note.strip():
        db.execute("DELETE FROM annotations WHERE doi = ?", (doi,))
        db.commit()
        return {"doi": doi, "tags": [], "note": "", "updated_at": None}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO annotations (doi, note, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(doi) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at",
        (doi, body.note, now),
    )
    db.execute("DELETE FROM annotation_tags WHERE doi = ?", (doi,))
    db.executemany("INSERT INTO annotation_tags (doi, tag) VALUES (?, ?)", [(doi, t) for t in body.tags])
    db.commit()
    return read_annotations(db, doi)[0]


@app.delete("/api/annotations/{doi:path}", status_code=204)
def delete_annotation(doi: str, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM annotations WHERE doi = ?", (doi,))
    db.commit()
