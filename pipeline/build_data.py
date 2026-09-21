"""Build the viewer's sample dataset from the raw APS metadata + citations.

Nodes  = a small sample of APS papers published in 2016-2022, stratified by
         PhySH discipline and biased toward well-connected papers so the sample
         has visible citation structure.
Edges  = citations between two sampled papers.
Layout = UMAP over PhySH topics + citation structure (computed on the sample only).

Usage (from the repo root):
    python pipeline/build_data.py --aps-dir ../APS --n 2000
Parsed metadata (all 2016-2022 papers) is cached in pipeline/cache/ so re-runs are fast.
Output: frontend/public/data/graph.json
"""
import argparse
import html
import json
import os
import pickle
import re
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

YEAR_MIN, YEAR_MAX = 2016, 2022

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / "cache"
TAG = re.compile(r"<[^>]+>")


def plain(text):
    """Strip HTML/MathML tags from a title and tidy whitespace."""
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", text or ""))).strip()


def parse_file(path):
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception:
        return None
    date = d.get("date") or ""
    if not (str(YEAR_MIN) <= date[:4] <= str(YEAR_MAX)):
        return None
    affs = {a["id"]: a["name"] for a in d.get("affiliations", []) if "id" in a}
    physh = (d.get("classificationSchemes") or {}).get("physh") or {}
    j = d.get("journal", {})
    return {
        "doi": d["id"],
        "title": plain(d.get("title", {}).get("value")),
        "journal": j.get("id"),
        "journalName": j.get("name"),
        "journalAbbr": j.get("abbreviatedName"),
        "date": date,
        "type": d.get("articleType"),
        "volume": (d.get("volume") or {}).get("number"),
        "issue": (d.get("issue") or {}).get("number"),
        "page": d.get("pageStart"),
        "authors": [
            {"name": a.get("name", ""), "aff": [i for i in a.get("affiliationIds", []) if i in affs]}
            for a in d.get("authors", [])
            if a.get("type", "Person") == "Person" and a.get("name")
        ],
        "affiliations": affs,
        "disciplines": [x["label"] for x in physh.get("disciplines", [])],
        "concepts": [
            {"id": c["id"], "label": c["label"], "facet": (c.get("facet") or {}).get("label"),
             "primary": bool(c.get("primary"))}
            for c in physh.get("concepts", [])
        ],
    }


def parse_dir(d):
    out = []
    for name in os.listdir(d):
        if name.endswith(".json"):
            r = parse_file(os.path.join(d, name))
            if r:
                out.append(r)
    return out


def load_papers(aps_dir):
    cache = CACHE / "papers.pkl"
    if cache.exists():
        print("loading cached papers", cache)
        return pickle.load(open(cache, "rb"))
    meta = Path(aps_dir) / "aps-dataset-metadata-2022"
    dirs = [str(p) for p in meta.glob("*/*") if p.is_dir()]
    print(f"parsing {len(dirs)} volume folders ...")
    t = time.time()
    with Pool() as pool:
        papers = [r for chunk in pool.imap_unordered(parse_dir, dirs, chunksize=4) for r in chunk]
    papers.sort(key=lambda p: (p["date"], p["doi"]))
    print(f"  {len(papers):,} papers in {time.time() - t:.0f}s")
    CACHE.mkdir(exist_ok=True)
    pickle.dump(papers, open(cache, "wb"))
    return papers


def load_edges(aps_dir, doi_to_idx):
    """Return deduplicated (src=citing, dst=cited) index arrays with both ends in the node set."""
    df = pd.read_csv(Path(aps_dir) / "aps-dataset-citations-2022.csv")
    s = pd.Series(doi_to_idx)
    src, dst = df["citing_doi"].map(s), df["cited_doi"].map(s)
    ok = src.notna() & dst.notna()
    e = pd.DataFrame({"s": src[ok].astype(np.int64), "d": dst[ok].astype(np.int64)})
    e = e[e.s != e.d].drop_duplicates()
    print(f"  {len(e):,} internal citation edges")
    return e.s.to_numpy(), e.d.to_numpy()


def choose_sample(papers, src, dst, n, seed=7):
    """Two-stage sample: stratified-by-discipline seeds, then the papers most linked to those seeds."""
    rng = np.random.default_rng(seed)
    N = len(papers)
    deg = np.bincount(src, minlength=N) + np.bincount(dst, minlength=N)
    pool = np.array([i for i, p in enumerate(papers) if p["disciplines"] and p["authors"] and deg[i] >= 5])
    disc = np.array([papers[i]["disciplines"][0] for i in pool])
    names, counts = np.unique(disc, return_counts=True)
    n_seed = n // 3
    picked = []
    for d, c in zip(names, counts):
        idx = pool[disc == d]
        w = deg[idx].astype(float) ** 1.5
        k = min(max(8, round(n_seed * c / counts.sum())), len(idx))
        picked += rng.choice(idx, size=k, replace=False, p=w / w.sum()).tolist()
    seeds = np.array(picked)
    in_seed = np.zeros(N, dtype=bool)
    in_seed[seeds] = True
    # links from every candidate paper into the seed set (either direction)
    links = np.bincount(src[in_seed[dst]], minlength=N) + np.bincount(dst[in_seed[src]], minlength=N)
    ok = np.zeros(N, dtype=bool)
    ok[pool] = True
    links[in_seed | ~ok] = -1
    fill = []
    for d, c in zip(names, counts):  # fill quota per discipline, most-linked papers first
        idx = pool[(disc == d) & ~in_seed[pool]]
        k = min(round((n - len(seeds)) * c / counts.sum()), len(idx))
        fill += idx[np.argsort(-links[idx], kind="stable")[:k]].tolist()
    return np.sort(np.concatenate([seeds, fill])).astype(int), deg


def compute_layout(papers, src, dst, seed=42):
    import umap
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    n = len(papers)
    cid, rows, cols = {}, [], []
    for i, p in enumerate(papers):
        for c in p["concepts"]:
            rows.append(i)
            cols.append(cid.setdefault(c["id"], len(cid)))
    X = sp.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(n, len(cid)))
    df = np.asarray((X > 0).sum(axis=0)).ravel()
    X = X.multiply(np.log((1 + n) / (1 + df)).astype(np.float32)).tocsr()
    F1 = normalize(TruncatedSVD(32, random_state=seed).fit_transform(normalize(X)))
    A = sp.coo_matrix((np.ones(len(src), dtype=np.float32), (src, dst)), shape=(n, n))
    A = ((A + A.T) > 0).astype(np.float32).tocsr()
    dinv = sp.diags(1 / np.sqrt(np.maximum(np.asarray(A.sum(axis=1)).ravel(), 1)))
    F2 = normalize(TruncatedSVD(16, random_state=seed).fit_transform(dinv @ A @ dinv))
    F = np.hstack([F1, 0.7 * F2]) + 1e-6  # epsilon keeps all-zero rows valid for cosine
    xy = umap.UMAP(n_neighbors=15, min_dist=0.5, spread=1.5, metric="cosine", random_state=seed).fit_transform(F)
    xy -= np.median(xy, axis=0)
    return (xy / np.percentile(np.abs(xy), 99) * 100).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aps-dir", default=str(ROOT.parent / "APS"))
    ap.add_argument("--n", type=int, default=2000, help="approximate sample size")
    ap.add_argument("--out", default=str(ROOT / "frontend" / "public" / "data" / "graph.json"))
    a = ap.parse_args()

    papers = load_papers(a.aps_dir)
    src, dst = load_edges(a.aps_dir, {p["doi"]: i for i, p in enumerate(papers)})
    indeg_all = np.bincount(dst, minlength=len(papers))
    keep, _ = choose_sample(papers, src, dst, a.n)

    remap = -np.ones(len(papers), dtype=np.int64)
    remap[keep] = np.arange(len(keep))
    m = (remap[src] >= 0) & (remap[dst] >= 0)
    s, d = remap[src[m]], remap[dst[m]]
    sample = [papers[i] for i in keep]
    isolated = len(sample) - len(np.unique(np.concatenate([s, d])))
    print(f"sample: {len(sample):,} papers, {len(s):,} citation edges, {isolated} isolated")

    xy = compute_layout(sample, s, d)
    nodes = []
    for i, (p, g) in enumerate(zip(sample, keep)):
        nodes.append({
            "id": i, "doi": p["doi"], "title": p["title"], "date": p["date"], "type": p["type"],
            "journal": p["journalName"], "abbr": p["journalAbbr"], "journalId": p["journal"],
            "volume": p["volume"], "issue": p["issue"], "page": p["page"],
            "authors": [{"name": x["name"], "aff": [p["affiliations"][j] for j in x["aff"]]} for x in p["authors"]],
            "discipline": p["disciplines"][0], "disciplines": p["disciplines"],
            "concepts": [{k: c[k] for k in ("label", "facet", "primary")} for c in p["concepts"]],
            "cited": int(indeg_all[g]),  # citations from all 2016-2022 APS papers, not just the sample
            "x": round(float(xy[i, 0]), 3), "y": round(float(xy[i, 1]), 3),
        })
    disciplines = pd.Series([n_["discipline"] for n_ in nodes]).value_counts().index.tolist()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"disciplines": disciplines, "nodes": nodes, "edges": np.stack([s, d], 1).tolist()},
                              ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
