"""Build the node-classification dataset from graph.json: features, labels and a fixed train/val/test split.

Task: predict a paper's PhySH *discipline* (its top-level research field) from
  1. its title (TF-IDF),
  2. its journal (one-hot), and
  3. the average title TF-IDF of its citation neighbours (one round of message passing).
The discipline / concepts / UMAP coordinates are never used as inputs (they would leak the label).
"""
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
GRAPH_JSON = ROOT / "frontend" / "public" / "data" / "graph.json"
N_CLASSES_KEPT = 8  # the 8 largest disciplines keep their own class; the rest are merged into "Other"
OTHER = "Other"
SEED = 0


def load_graph(path=GRAPH_JSON):
    return json.loads(Path(path).read_text())


def build_labels(nodes):
    counts = {}
    for n in nodes:
        counts[n["discipline"]] = counts.get(n["discipline"], 0) + 1
    kept = sorted(counts, key=counts.get, reverse=True)[:N_CLASSES_KEPT]
    classes = kept + [OTHER]
    y = np.array([classes.index(n["discipline"]) if n["discipline"] in kept else len(kept) for n in nodes])
    return y, classes


def make_split(y, seed=SEED):
    """Stratified 70 / 15 / 15 split. Returns three index arrays."""
    idx = np.arange(len(y))
    train, rest = train_test_split(idx, test_size=0.30, stratify=y, random_state=seed)
    val, test = train_test_split(rest, test_size=0.50, stratify=y[rest], random_state=seed)
    return train, val, test


def build_features(graph, train_idx, use_journal=True, use_neighbors=True, max_features=1500):
    """Return a float32 matrix [n_papers, n_features]. TF-IDF vocabulary is fit on training papers only."""
    nodes, n = graph["nodes"], len(graph["nodes"])
    titles = [x["title"] for x in nodes]
    tfidf = TfidfVectorizer(max_features=max_features, min_df=2, stop_words="english", sublinear_tf=True)
    tfidf.fit([titles[i] for i in train_idx])
    X_title = tfidf.transform(titles).toarray().astype(np.float32)
    parts = [X_title]
    if use_neighbors:
        A = np.zeros((n, n), dtype=np.float32)  # undirected citation adjacency, row-normalised
        for a, b in graph["edges"]:
            A[a, b] = A[b, a] = 1
        deg = A.sum(1, keepdims=True)
        parts.append(np.divide(A @ X_title, deg, out=np.zeros_like(X_title), where=deg > 0))
    if use_journal:
        journals = sorted({x["abbr"] for x in nodes})
        parts.append(np.array([[x["abbr"] == j for j in journals] for x in nodes], dtype=np.float32))
    return np.concatenate(parts, axis=1)


def load_dataset(graph=None, **feature_kwargs):
    graph = graph or load_graph()
    y, classes = build_labels(graph["nodes"])
    train, val, test = make_split(y)
    X = build_features(graph, train, **feature_kwargs)
    return {"X": X, "y": y, "classes": classes, "train": train, "val": val, "test": test}
