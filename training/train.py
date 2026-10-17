"""Training loop (forward -> loss -> backprop -> gradient step) and a command-line entry point.

    python training/train.py            # trains with the defaults and writes backend/model/*

The loop in `train_model` is also called by the backend when the user trains interactively from the web app.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from torch import nn

sys.path.insert(0, str(Path(__file__).parent))
from data import load_dataset  # noqa: E402
from model import MLP  # noqa: E402

MODEL_DIR = Path(__file__).resolve().parents[1] / "backend" / "model"
DEFAULTS = {"lr": 0.001, "epochs": 40, "hidden": 64, "n_layers": 1, "activation": "relu",
            "dropout": 0.3, "weight_decay": 1e-3, "optimizer": "adam", "batch_size": 64}
LIMITS = {"lr": (1e-5, 1.0), "epochs": (1, 300), "hidden": (2, 512), "n_layers": (1, 4),
          "dropout": (0.0, 0.9), "weight_decay": (0.0, 0.1), "batch_size": (8, 512)}


def clean_hparams(hp):
    """Merge user-supplied hyper-parameters with the defaults and clamp them to sane ranges."""
    out = {**DEFAULTS, **{k: v for k, v in (hp or {}).items() if v is not None}}
    for k, (lo, hi) in LIMITS.items():
        out[k] = min(max(type(DEFAULTS[k])(out[k]), lo), hi)
    if out["activation"] not in ("relu", "tanh", "sigmoid", "leaky_relu"):
        raise ValueError("unknown activation")
    if out["optimizer"] not in ("adam", "sgd"):
        raise ValueError("unknown optimizer")
    return out


@torch.no_grad()
def evaluate(model, X, y, loss_fn):
    model.eval()
    logits = model(X)
    pred = logits.argmax(1)
    return loss_fn(logits, y).item(), (pred == y).float().mean().item(), pred.numpy()


def train_model(data, hp, on_epoch=None, should_stop=lambda: False, seed=0):
    """Train an MLP. `on_epoch(record)` is called after every epoch (used for the live training monitor)."""
    hp = clean_hparams(hp)
    torch.manual_seed(seed)
    X, y = torch.tensor(data["X"]), torch.tensor(data["y"])
    tr, va, te = (torch.tensor(data[k]) for k in ("train", "val", "test"))
    model = MLP(X.shape[1], len(data["classes"]), hp["hidden"], hp["n_layers"], hp["activation"], hp["dropout"])  # 1. init
    loss_fn = nn.CrossEntropyLoss()
    opt = (torch.optim.Adam if hp["optimizer"] == "adam" else
           lambda p, **kw: torch.optim.SGD(p, momentum=0.9, **kw))(model.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"])
    history, best = [], (float("inf"), None)
    for epoch in range(1, hp["epochs"] + 1):
        if should_stop():
            break
        model.train()
        for b in tr[torch.randperm(len(tr))].split(hp["batch_size"]):
            opt.zero_grad()
            loss = loss_fn(model(X[b]), y[b])  # 2. forward pass  3. loss
            loss.backward()                    # 4. backpropagation -> 5. gradients in p.grad
            opt.step()                         # 6. gradient-descent update
        rec = {"epoch": epoch}
        for name, idx in (("train", tr), ("val", va), ("test", te)):
            rec[f"{name}_loss"], rec[f"{name}_acc"], _ = evaluate(model, X[idx], y[idx], loss_fn)
        history.append(rec)
        if rec["val_loss"] < best[0]:  # keep the weights with the lowest validation loss (early-stopping style)
            best = (rec["val_loss"], {k: v.clone() for k, v in model.state_dict().items()})
        if on_epoch:
            on_epoch(rec)
    if best[1] is not None:
        model.load_state_dict(best[1])
    return model, history, hp


def final_metrics(model, data):
    X, y = torch.tensor(data["X"]), torch.tensor(data["y"])
    loss_fn, out = nn.CrossEntropyLoss(), {}
    for name in ("train", "val", "test"):
        idx = torch.tensor(data[name])
        loss, acc, pred = evaluate(model, X[idx], y[idx], loss_fn)
        out[name] = {"loss": loss, "accuracy": acc, "error": 1 - acc,
                     "macro_f1": float(f1_score(data["y"][data[name]], pred, average="macro"))}
    return out


def baselines(data):
    """Shallow benchmarks on the same features: majority class and logistic regression (no hidden layer)."""
    out = {}
    for name, clf in (("majority_class", DummyClassifier(strategy="most_frequent")),
                      ("logistic_regression", LogisticRegression(max_iter=2000, C=10))):
        clf.fit(data["X"][data["train"]], data["y"][data["train"]])
        pred = clf.predict(data["X"][data["test"]])
        acc = float((pred == data["y"][data["test"]]).mean())
        out[name] = {"accuracy": acc, "error": 1 - acc, "macro_f1": float(f1_score(data["y"][data["test"]], pred, average="macro"))}
    return out


def save_model(model, hp, data, history, metrics, bl, directory=MODEL_DIR):
    directory.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hparams": hp, "n_in": data["X"].shape[1], "classes": data["classes"]},
               directory / "model.pt")
    (directory / "metrics.json").write_text(json.dumps(
        {"hparams": hp, "classes": data["classes"], "metrics": metrics, "baselines": bl, "history": history,
         "split_sizes": {k: int(len(data[k])) for k in ("train", "val", "test")}}, indent=1))


def plot_curves(history, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ep = [h["epoch"] for h in history]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for k in ("train", "val"):
        ax[0].plot(ep, [h[f"{k}_loss"] for h in history], label=k)
        ax[1].plot(ep, [h[f"{k}_acc"] for h in history], label=k)
    ax[0].set(title="Loss vs epoch", xlabel="epoch", ylabel="cross-entropy")
    ax[1].set(title="Accuracy vs epoch", xlabel="epoch", ylabel="accuracy")
    for a in ax:
        a.legend(); a.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(path, dpi=150)


if __name__ == "__main__":
    data = load_dataset()
    t = time.time()
    model, history, hp = train_model(data, {}, on_epoch=lambda r: print(
        f"epoch {r['epoch']:3d}  train loss {r['train_loss']:.3f} acc {r['train_acc']:.3f} | val loss {r['val_loss']:.3f} acc {r['val_acc']:.3f}"))
    metrics, bl = final_metrics(model, data), baselines(data)
    save_model(model, hp, data, history, metrics, bl)
    plot_curves(history, MODEL_DIR / "loss_curve.png")
    print(f"\ntrained in {time.time() - t:.1f}s; classes: {data['classes']}")
    print("MLP     ", json.dumps(metrics))
    print("baseline", json.dumps(bl))
