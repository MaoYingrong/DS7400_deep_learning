"""HW3 experiments: HW2 baseline vs. the weight-tied gated two-branch design and its ablations.

    python training/hw3_experiments.py            # runs everything in hw3_config.json, writes results/hw3/results.json
    python training/hw3_experiments.py --epochs 80 --only baseline,tied_gated --tag ep80   # training-budget check
    python training/hw3_analyze.py                # table + figures from the saved results

Everything except the model is held fixed: same features, same stratified split (seed 0), same optimiser (Adam),
learning rate, weight decay, batch size, epochs and best-validation-epoch selection as HW2. Each variant is trained
with 10 seeds (initialisation + batch order) because 300 test papers make a single run noisy.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn

sys.path.insert(0, str(Path(__file__).parent))
from data import load_dataset, load_graph  # noqa: E402
from hw3_model import GatedBranchNet, count_params  # noqa: E402
from model import MLP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "hw3"
CONFIG = json.loads((Path(__file__).parent / "hw3_config.json").read_text())


def build_model(spec, n_in, n_text, n_classes, hp):
    if spec["model"] == "hw2_mlp":  # exactly the HW2 network
        return MLP(n_in, n_classes, hp["hidden"], 1, "relu", hp["dropout"])
    return GatedBranchNet(n_text, n_in - 2 * n_text, n_classes, hp["hidden"], hp["dropout"], spec["tied"], spec["gate"])


def run(spec, data, n_text, hp, seed):
    """Same loop as HW2's train_model (forward -> loss -> backward -> step, keep the best-validation epoch)."""
    torch.manual_seed(seed)
    X, y = torch.tensor(data["X"]), torch.tensor(data["y"])
    idx = {k: torch.tensor(data[k]) for k in ("train", "val", "test")}
    model = build_model(spec, X.shape[1], n_text, len(data["classes"]), hp)
    loss_fn = nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.parameters(), lr=hp["lr"], weight_decay=hp["weight_decay"])
    history, best, t0 = [], (float("inf"), None, 0), time.time()
    for epoch in range(1, hp["epochs"] + 1):
        model.train()
        for b in idx["train"][torch.randperm(len(idx["train"]))].split(hp["batch_size"]):
            opt.zero_grad()
            loss_fn(model(X[b]), y[b]).backward()
            opt.step()
        model.eval()
        rec = {"epoch": epoch}
        with torch.no_grad():
            for k, i in idx.items():
                logits = model(X[i])
                rec[f"{k}_loss"] = loss_fn(logits, y[i]).item()
                rec[f"{k}_acc"] = (logits.argmax(1) == y[i]).float().mean().item()
                if k == "train" and isinstance(model, GatedBranchNet):
                    rec["gate_mean"] = model.last_gate.mean().item()
        history.append(rec)
        if rec["val_loss"] < best[0]:
            best = (rec["val_loss"], {k: v.clone() for k, v in model.state_dict().items()}, epoch)
    seconds = time.time() - t0
    model.load_state_dict(best[1])
    model.eval()
    out = {"seed": seed, "best_epoch": best[2], "seconds": seconds, "params": count_params(model), "history": history}
    with torch.no_grad():
        for k, i in idx.items():
            logits = model(X[i])
            pred = logits.argmax(1)
            out[f"{k}_loss"] = loss_fn(logits, y[i]).item()
            out[f"{k}_acc"] = (pred == y[i]).float().mean().item()
            out[f"{k}_f1"] = float(f1_score(y[i].numpy(), pred.numpy(), average="macro"))
        if isinstance(model, GatedBranchNet):
            model(X)
            out["gate_all"] = [round(v, 4) for v in model.last_gate.squeeze(1).tolist()]
            out["pred_all"] = model(X).argmax(1).tolist()
    return out


def summarise(runs):
    s = {"params": runs[0]["params"]}
    for k in ("train_acc", "val_acc", "test_acc", "test_f1", "train_loss", "val_loss", "test_loss", "best_epoch", "seconds"):
        v = np.array([r[k] for r in runs])
        s[k], s[k + "_std"] = float(v.mean()), float(v.std(ddof=1))
    gap = np.array([r["train_acc"] - r["val_acc"] for r in runs])
    s["gap"], s["gap_std"] = float(gap.mean()), float(gap.std(ddof=1))
    last = np.array([r["history"][-1]["train_acc"] - r["history"][-1]["val_acc"] for r in runs])
    s["gap_final_epoch"] = float(last.mean())
    return s


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--only", help="comma-separated variant names")
    ap.add_argument("--tag", default="", help="suffix for the output file")
    args = ap.parse_args()
    if args.epochs:
        CONFIG["hparams"]["epochs"] = args.epochs
    if args.only:
        CONFIG["variants"] = {k: CONFIG["variants"][k] for k in args.only.split(",")}
    graph = load_graph()
    data = load_dataset(graph)
    n_journal = len({n["abbr"] for n in graph["nodes"]})
    n_text = (data["X"].shape[1] - n_journal) // 2
    hp, seeds = CONFIG["hparams"], CONFIG["seeds"]
    degree = np.zeros(len(graph["nodes"]), dtype=int)
    for a, b in graph["edges"]:
        degree[a] += 1
        degree[b] += 1
    print(f"inputs: {n_text} title + {n_text} neighbour + {n_journal} journal = {data['X'].shape[1]}")
    results = {"config": CONFIG, "n_text": n_text, "n_journal": n_journal, "degree": degree.tolist(),
               "split": {k: data[k].tolist() for k in ("train", "val", "test")}, "y": data["y"].tolist(),
               "classes": data["classes"], "runs": {}, "summary": {}}
    for name, spec in CONFIG["variants"].items():
        runs = [run(spec, data, n_text, hp, s) for s in seeds]
        results["runs"][name], results["summary"][name] = runs, summarise(runs)
        s = results["summary"][name]
        print(f"{name:14s} params {s['params']:7d} | train {s['train_acc']:.3f} val {s['val_acc']:.3f} "
              f"test {s['test_acc']:.3f}±{s['test_acc_std']:.3f} F1 {s['test_f1']:.3f} | gap {s['gap']:.3f} | best ep {s['best_epoch']:.1f}")
    base = np.array([r["test_acc"] for r in results["runs"]["baseline"]])
    for name in CONFIG["variants"]:  # paired difference vs baseline over the same seeds
        d = np.array([r["test_acc"] for r in results["runs"][name]]) - base
        results["summary"][name]["diff_vs_baseline"] = float(d.mean())
        results["summary"][name]["diff_se"] = float(d.std(ddof=1) / np.sqrt(len(d)))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"results{'_' + args.tag if args.tag else ''}.json"
    path.write_text(json.dumps(results))
    print("wrote", path)


if __name__ == "__main__":
    main()
