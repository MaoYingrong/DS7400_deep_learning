"""Neural-network service: holds the active model, answers predictions, and trains in a background thread.

The shipped weights (backend/model/model.pt, made by training/train.py) are loaded at startup. Training from the web app
replaces the *in-memory* model only; "reset" restores the shipped weights. Nothing the user trains overwrites model.pt.
"""
import json
import os
import sys
import threading
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "training"))
from data import GRAPH_JSON, load_dataset, load_graph  # noqa: E402
from model import MLP  # noqa: E402
from train import DEFAULTS, LIMITS, baselines, clean_hparams, final_metrics, train_model  # noqa: E402

MODEL_DIR = ROOT / "backend" / "model"


class MLService:
    def __init__(self):
        self.lock = threading.Lock()
        self.graph = load_graph(os.environ.get("GRAPH_JSON", GRAPH_JSON))
        self.data = load_dataset(self.graph)
        self.doi_to_idx = {n["doi"]: i for i, n in enumerate(self.graph["nodes"])}
        split = np.empty(len(self.data["y"]), dtype=object)
        for name in ("train", "val", "test"):
            split[self.data[name]] = name
        self.split = split
        self.baselines = baselines(self.data)
        self.job = {"running": False, "epoch": 0, "epochs": 0, "history": [], "hparams": None, "error": None}
        self.stop_flag = threading.Event()
        self.load_pretrained()

    # ---- model state -------------------------------------------------
    def load_pretrained(self):
        ckpt = torch.load(MODEL_DIR / "model.pt")
        hp = ckpt["hparams"]
        model = MLP(ckpt["n_in"], len(ckpt["classes"]), hp["hidden"], hp["n_layers"], hp["activation"], hp["dropout"])
        model.load_state_dict(ckpt["state_dict"])
        saved = json.loads((MODEL_DIR / "metrics.json").read_text())
        self._set_active(model, hp, saved["metrics"], saved["history"], source="pretrained")

    def _set_active(self, model, hp, metrics, history, source):
        model.eval()
        with torch.no_grad():
            probs = torch.softmax(model(torch.tensor(self.data["X"])), 1).numpy()
        with self.lock:
            self.model, self.hp, self.metrics, self.history, self.source, self.probs = model, hp, metrics, history, source, probs

    # ---- queries -----------------------------------------------------
    def info(self):
        with self.lock:
            return {"source": self.source, "hparams": self.hp, "metrics": self.metrics, "baselines": self.baselines,
                    "history": self.history, "classes": self.data["classes"], "defaults": DEFAULTS,
                    "limits": LIMITS, "split_sizes": {k: int(len(self.data[k])) for k in ("train", "val", "test")}}

    def predict(self, doi, k=5):
        i = self.doi_to_idx.get(doi)
        if i is None:
            return None
        with self.lock:
            p, classes = self.probs[i], self.data["classes"]
        top = np.argsort(-p)[:k]
        true = int(self.data["y"][i])
        return {"doi": doi, "predicted": classes[top[0]], "confidence": float(p[top[0]]), "true": classes[true],
                "correct": bool(top[0] == true), "split": self.split[i],
                "top": [{"label": classes[j], "prob": float(p[j])} for j in top]}

    def all_predictions(self):
        """Per paper: predicted class index, confidence, true class index, split."""
        with self.lock:
            p = self.probs
        return {"classes": self.data["classes"], "pred": p.argmax(1).tolist(), "conf": np.round(p.max(1), 3).tolist(),
                "true": self.data["y"].tolist(), "split": self.split.tolist()}

    # ---- interactive training ---------------------------------------
    def start_training(self, hp):
        hp = clean_hparams(hp)
        with self.lock:
            if self.job["running"]:
                raise RuntimeError("training already running")
            self.stop_flag.clear()
            self.job = {"running": True, "epoch": 0, "epochs": hp["epochs"], "history": [], "hparams": hp, "error": None}
        threading.Thread(target=self._run, args=(hp,), daemon=True).start()
        return hp

    def stop_training(self):
        self.stop_flag.set()

    def _run(self, hp):
        def on_epoch(rec):
            with self.lock:
                self.job["epoch"] = rec["epoch"]
                self.job["history"].append(rec)
        try:
            model, history, hp = train_model(self.data, hp, on_epoch=on_epoch, should_stop=self.stop_flag.is_set)
            if history:
                self._set_active(model, hp, final_metrics(model, self.data), history, source="trained in app")
        except Exception as e:  # report to the UI instead of dying silently
            with self.lock:
                self.job["error"] = str(e)
        finally:
            with self.lock:
                self.job["running"] = False

    def status(self):
        with self.lock:
            return {**self.job, "history": list(self.job["history"])}
