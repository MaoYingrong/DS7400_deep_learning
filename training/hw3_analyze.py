"""Turn results/hw3/results.json into a summary table and figures (run after hw3_experiments.py)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "results" / "hw3"
LABELS = {"baseline": "HW2 baseline (untied, fixed add)", "tied_gated": "Tied + per-paper gate (my design)",
          "tied_add": "Tied, fixed add (no gate)", "untied_gated": "Untied + per-paper gate",
          "tied_scalar": "Tied + one global gate", "no_neighbors": "Tied, neighbour branch removed"}
COLORS = {"baseline": "#444444", "tied_gated": "#c0392b", "tied_add": "#2471a3", "untied_gated": "#b9770e"}


def table(res, title):
    rows = [f"### {title}", "",
            "| Variant | Params | Train acc | Val acc | Test acc | Test macro-F1 | Train-val gap | Test diff vs baseline | Best epoch |",
            "|---|---|---|---|---|---|---|---|---|"]
    for k, s in res["summary"].items():
        rows.append(f"| {LABELS[k]} | {s['params']:,} | {100*s['train_acc']:.1f} | {100*s['val_acc']:.1f} ± {100*s['val_acc_std']:.1f} | "
                    f"{100*s['test_acc']:.1f} ± {100*s['test_acc_std']:.1f} | {s['test_f1']:.3f} ± {s['test_f1_std']:.3f} | "
                    f"{100*s['gap']:.1f} | {100*s['diff_vs_baseline']:+.1f} ± {100*s['diff_se']:.1f} | {s['best_epoch']:.1f} |")
    return "\n".join(rows)


def mean_curve(runs, key):
    return np.mean([[h[key] for h in r["history"]] for r in runs], axis=0)


def main():
    res = json.loads((OUT / "results.json").read_text())
    n_seeds = len(res["config"]["seeds"])
    md = [table(res, f"Main experiment: {res['config']['hparams']['epochs']} epochs, mean ± std over {n_seeds} seeds "
                     "(accuracy in %, test diff = paired mean ± standard error)")]

    # ---- training curves ----
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.7))
    for k, c in COLORS.items():
        runs = res["runs"][k]
        ep = np.arange(1, len(runs[0]["history"]) + 1)
        ax[0].plot(ep, mean_curve(runs, "train_loss"), c=c, ls="--", lw=1.2)
        ax[0].plot(ep, mean_curve(runs, "val_loss"), c=c, label=LABELS[k])
        ax[1].plot(ep, mean_curve(runs, "train_acc") - mean_curve(runs, "val_acc"), c=c)
        ax[2].plot(ep, mean_curve(runs, "val_acc"), c=c)
    ax[0].set(title="Loss (dashed = train, solid = validation)", xlabel="epoch", ylabel="cross-entropy")
    ax[1].set(title="Overfitting gap: train acc − val acc", xlabel="epoch")
    ax[2].set(title="Validation accuracy", xlabel="epoch", ylim=(0.5, 0.8))
    ax[0].legend(fontsize=7.5)
    for a in ax:
        a.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(OUT / "curves.png", dpi=150); plt.close(fig)

    # ---- what did the gate learn? ----
    deg = np.array(res["degree"]); y = np.array(res["y"]); test = np.array(res["split"]["test"])
    md.append("\n### Gate diagnostics (per-paper gate g, all 2,000 papers, final weights)\n")
    md.append("| Variant | mean g | std of g across papers | min | max | corr(g, log(1+degree)) | mean g, degree 0 | test: g when correct | test: g when wrong |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.7))
    for j, k in enumerate(("tied_gated", "untied_gated")):
        G = np.array([r["gate_all"] for r in res["runs"][k]])            # [seeds, papers]
        P = np.array([r["pred_all"] for r in res["runs"][k]])
        ok = P[:, test] == y[test]
        g = G.mean(0)
        iso = deg == 0
        md.append(f"| {LABELS[k]} | {G.mean():.3f} | {G.std(1).mean():.3f} | {G.min():.3f} | {G.max():.3f} | "
                  f"{np.mean([np.corrcoef(row, np.log1p(deg))[0, 1] for row in G]):+.2f} | "
                  f"{(G[:, iso].mean() if iso.any() else float('nan')):.3f} (n={int(iso.sum())}) | "
                  f"{G[:, test][ok].mean():.3f} | {G[:, test][~ok].mean():.3f} |")
        ax[0].hist(g, bins=40, alpha=.6, label=LABELS[k], color=COLORS[k])
        ax[1].scatter(deg + 1, g, s=4, alpha=.35, color=COLORS[k], label=LABELS[k])
    ep = np.arange(1, len(res["runs"]["tied_gated"][0]["history"]) + 1)
    for k in ("tied_gated", "untied_gated", "tied_scalar"):
        ax[2].plot(ep, mean_curve(res["runs"][k], "gate_mean"), label=LABELS[k], color=COLORS.get(k, "#1e8449"))
    ax[0].set(title="Gate value per paper (mean over seeds)", xlabel="g", xlim=(0, 1)); ax[0].legend(fontsize=7.5)
    ax[1].set(title="Gate vs. number of citation neighbours", xlabel="degree + 1", ylabel="g", xscale="log", ylim=(0, 1))
    ax[2].set(title="Mean gate on training papers during training", xlabel="epoch", ylim=(0, 1)); ax[2].legend(fontsize=7.5)
    for a in ax:
        a.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(OUT / "gates.png", dpi=150); plt.close(fig)

    # ---- per-degree accuracy: who benefits from neighbours? ----
    md.append("\n### Test accuracy by number of citation neighbours (mean over seeds, %)\n")
    bins = [(0, 5), (6, 15), (16, 30), (31, 10**6)]
    md.append("| Variant | " + " | ".join(f"degree {a}–{b if b < 10**6 else '∞'} (n={int(((deg[test] >= a) & (deg[test] <= b)).sum())})" for a, b in bins) + " |")
    md.append("|---|" + "---|" * len(bins))
    for k in ("tied_gated", "tied_add", "untied_gated", "tied_scalar", "no_neighbors"):
        P = np.array([r["pred_all"] for r in res["runs"][k]])[:, test]
        cells = [f"{100 * (P[:, (deg[test] >= a) & (deg[test] <= b)] == y[test][(deg[test] >= a) & (deg[test] <= b)]).mean():.1f}" for a, b in bins]
        md.append(f"| {LABELS[k]} | " + " | ".join(cells) + " |")

    extra = OUT / "results_ep80.json"
    if extra.exists():
        r2 = json.loads(extra.read_text())
        md.append("\n" + table(r2, f"Training-budget check: {r2['config']['hparams']['epochs']} epochs (same seeds)"))
        md.append("\nFinal-epoch train−val gap (no best-epoch selection): " + ", ".join(
            f"{LABELS[k]} {100*s['gap_final_epoch']:.1f}" for k, s in r2["summary"].items()))
    md.append("\nFinal-epoch train−val gap in the main experiment: " + ", ".join(
        f"{LABELS[k]} {100*s['gap_final_epoch']:.1f}" for k, s in res["summary"].items()))
    md.append("\nMean training time per run (s): " + ", ".join(f"{LABELS[k]} {s['seconds']:.2f}" for k, s in res["summary"].items()))
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
