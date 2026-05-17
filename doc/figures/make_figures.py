"""Generate the 6 figures referenced in doc/35_FINAL_REPORT.md.

All labels use conceptual / descriptive names rather than repo-internal
identifiers (v3, v4, file paths, script names, phase names), so that the
figures stand alone for a reader without access to the source repository.

Output: PNG files in this directory at 300 DPI, sized for a US-letter PDF
column (max width ~6.5 in).

Run:
    "d:/.../lab3/.venv/Scripts/python.exe" doc/figures/make_figures.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D

OUT = Path(__file__).parent
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 300,
})


# =============================================================================
# Figure 1 — Baseline vs SCER head (side-by-side)
# =============================================================================

def fig1_head_comparison():
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.0, 4.4))
    fig.suptitle("Head Architecture Comparison", fontsize=11, y=0.99)

    def box(ax, x, y, w, h, text, fc="#e6f0fa", ec="#3a6da6", lw=1.2,
            fontsize=8, weight="normal"):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04",
            linewidth=lw, edgecolor=ec, facecolor=fc,
        ))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, fontweight=weight)

    def arrow(ax, x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="-|>", mutation_scale=12,
            linewidth=1.0, color="#444",
        ))

    # ---- left: baseline ----
    ax = axL
    ax.set_xlim(0, 5); ax.set_ylim(-1.2, 10); ax.axis("off")
    ax.set_title("Baseline — single-stage classifier",
                 color="#a4413f", fontsize=10)
    box(ax, 1.0, 8.4, 3.0, 0.8, "image (1, 3, 128, 128)", fc="#fff1d6")
    arrow(ax, 2.5, 8.4, 2.5, 7.7)
    box(ax, 0.5, 6.7, 4.0, 1.0, "ResNet-18 backbone\n(11 M params, 9 MB INT8)")
    arrow(ax, 2.5, 6.7, 2.5, 6.0)
    box(ax, 1.0, 5.0, 3.0, 1.0,
        "feat (1, 512)\nshared 512-d feature", fc="#e8eef5")
    arrow(ax, 2.5, 5.0, 2.5, 4.3)
    box(ax, 0.3, 2.7, 4.4, 1.6,
        "Linear(512 -> 98 169)\n50 MB FC head\n+ softmax CE",
        fc="#fde2e1", ec="#a4413f", lw=1.5, weight="bold")
    arrow(ax, 2.5, 2.7, 2.5, 2.0)
    box(ax, 1.0, 1.0, 3.0, 1.0, "argmax over 98 169 logits\n-> top-K")
    ax.text(2.5, 0.2,
            "59 MB INT8 total · 87 % off-chip · INT8 corrupt",
            ha="center", fontsize=8, color="#a4413f", style="italic")

    # ---- right: SCER ----
    ax = axR
    ax.set_xlim(0, 5); ax.set_ylim(-1.2, 10); ax.axis("off")
    ax.set_title("SCER — embedding + external cosine NN",
                 color="#2a7d2e", fontsize=10)
    box(ax, 1.0, 8.4, 3.0, 0.8, "image (1, 3, 128, 128)", fc="#fff1d6")
    arrow(ax, 2.5, 8.4, 2.5, 7.7)
    box(ax, 0.5, 6.7, 4.0, 1.0, "ResNet-18 backbone\n(11 M params, 9 MB INT8)")
    arrow(ax, 2.5, 6.7, 2.5, 6.0)
    box(ax, 1.0, 5.0, 3.0, 1.0,
        "feat (1, 512)", fc="#e8eef5")
    # branch into embedding + 4 structure heads
    box(ax, 0.1, 3.2, 2.1, 1.4,
        "embedding head\nLinear(512 -> 128)\n+ L2-norm",
        fc="#dff3e0", ec="#2a7d2e", lw=1.5, weight="bold", fontsize=7.5)
    box(ax, 2.5, 3.2, 2.4, 1.4,
        "4 structure heads\n(radical 214 /\nstrokes x2 / IDC 12)\nfor multi-stage filter",
        fc="#f0f0f0", fontsize=7)
    arrow(ax, 2.5, 5.0, 1.15, 4.6)
    arrow(ax, 2.5, 5.0, 3.7, 4.6)
    arrow(ax, 1.15, 3.2, 1.15, 2.5)
    box(ax, 0.1, 1.3, 2.1, 1.2,
        "external anchor DB\n(98 169, 128) FP32\nloaded once at startup",
        fc="#fff1d6", ec="#cc8a1a", lw=1.5, fontsize=7.5)
    arrow(ax, 1.15, 1.3, 2.5, 0.6)
    box(ax, 1.5, -0.3, 2.0, 0.9,
        "cosine NN -> top-K\n(numpy on host CPU)",
        fc="#dff3e0", ec="#2a7d2e", lw=1.2, weight="bold", fontsize=7.5)
    ax.text(2.5, -0.95,
            "11 MB INT8 graph · 47 MB anchor DB · 0.00 pp loss",
            ha="center", fontsize=8, color="#2a7d2e", style="italic")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT / "fig1_head_comparison.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig1_head_comparison.png")


# =============================================================================
# Figure 2 — Full SCER training + inference graph
# =============================================================================

def fig2_scer_full():
    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    ax.set_xlim(0, 14); ax.set_ylim(0, 9.5); ax.axis("off")
    ax.set_title("SCER Architecture", fontsize=11, pad=10)

    def box(x, y, w, h, text, fc="#e6f0fa", ec="#3a6da6", lw=1.2,
            fontsize=8, weight="normal"):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04",
            linewidth=lw, edgecolor=ec, facecolor=fc,
        ))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, fontweight=weight)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10,
            linewidth=1.0, color="#444",
        ))

    # input + backbone (top row)
    box(0.3, 7.9, 2.2, 0.9, "image\n(1, 3, 128, 128)", fc="#fff1d6")
    arrow(2.5, 8.35, 3.3, 8.35)
    box(3.3, 7.7, 2.6, 1.3, "ResNet-18\nbackbone\n(11 M params)", weight="bold")
    arrow(5.9, 8.35, 6.7, 8.35)
    box(6.7, 7.9, 1.8, 0.9, "feat (512)", fc="#e8eef5")

    # 4 structure heads (right column, vertical stack)
    head_x = 8.8
    head_w = 5.0
    head_h = 0.7
    heads_y = [7.7, 6.8, 5.9, 5.0]
    heads_txt = [
        "radical_head: Linear(512, 214), CE α=0.10",
        "total_strokes: Linear(512, 1), MSE α=0.05",
        "residual_strokes: Linear(512, 1), MSE α=0.05",
        "idc_head: Linear(512, 12), CE α=0.10",
    ]
    for y, txt in zip(heads_y, heads_txt):
        box(head_x, y, head_w, head_h, txt, fc="#f0f0f0", fontsize=6.8)
        arrow(8.5, 8.35, head_x, y + head_h / 2)

    # group label for structure heads
    ax.text(head_x + head_w / 2, 8.65, "auxiliary structure heads",
            ha="center", fontsize=7.5, color="#666", style="italic")

    # embedding head — center, prominent
    box(5.0, 3.4, 4.0, 1.0,
        "embedding_head\nLinear(512, 128) + L2-norm",
        fc="#dff3e0", ec="#2a7d2e", lw=1.6, weight="bold", fontsize=8.5)
    arrow(7.6, 7.9, 7.0, 4.4)  # from feat to embedding

    # comment about structure heads being kept at deploy — placed BELOW the
    # last head box, to the right of the embedding head; no longer overlaps
    # the feat -> embedding arrow path
    ax.text(11.65, 4.6,
            "(survive into deploy; soft\nmulti-stage filter at inference)",
            ha="center", fontsize=7, color="#666", style="italic")

    # train-time vs inference branches (bottom)
    tr_x, tr_y, tr_w, tr_h = 0.3, 0.4, 6.4, 2.2
    ax.add_patch(Rectangle((tr_x, tr_y), tr_w, tr_h,
                            linewidth=1.3, edgecolor="#a4413f",
                            facecolor="#fde2e1", alpha=0.35))
    ax.text(tr_x + 0.2, tr_y + tr_h - 0.25,
            "TRAINING TIME  (drop at deploy)",
            fontsize=8, fontweight="bold", color="#a4413f")
    box(tr_x + 0.4, tr_y + 0.45, 5.6, 1.20,
        "ArcFace classifier - weight (98 169, 128)\n"
        "scale s=30, margin m in [0.3, 0.5] curriculum\n"
        "-> softmax cross-entropy",
        fc="#fde2e1", ec="#a4413f", lw=1.0, fontsize=8)

    inf_x, inf_y, inf_w, inf_h = 7.2, 0.4, 6.5, 2.2
    ax.add_patch(Rectangle((inf_x, inf_y), inf_w, inf_h,
                            linewidth=1.3, edgecolor="#2a7d2e",
                            facecolor="#dff3e0", alpha=0.35))
    ax.text(inf_x + 0.2, inf_y + inf_h - 0.25,
            "INFERENCE TIME  (deploy)",
            fontsize=8, fontweight="bold", color="#2a7d2e")
    box(inf_x + 0.4, inf_y + 0.45, 5.7, 1.20,
        "cosine NN over external anchor DB\n"
        "(98 169, 128) FP32  matrix-multiply on host CPU\n"
        "-> argsort -> top-K characters",
        fc="#dff3e0", ec="#2a7d2e", lw=1.0, fontsize=8)

    # arrows from emb head to both branches
    arrow(6.5, 3.4, 4.5, 2.65)  # to training
    arrow(7.5, 3.4, 9.5, 2.65)  # to inference

    fig.savefig(OUT / "fig2_scer_full.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig2_scer_full.png")


# =============================================================================
# Figure 3 — Deploy pipeline flow
# =============================================================================

def fig3_deploy_pipeline():
    fig, ax = plt.subplots(figsize=(7.5, 6.0))
    ax.set_xlim(0, 14); ax.set_ylim(0, 13.5); ax.axis("off")
    ax.set_title("Deploy Workflow Summary", fontsize=11, pad=10)

    def stage(y, host, stage_name, artifact, gate, tools, fc="#e6f0fa",
              banner_color="#3a6da6"):
        x, w = 0.5, 13.0
        h = 1.7
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04",
            linewidth=1.3, edgecolor=banner_color, facecolor=fc,
        ))
        ax.text(x + 0.3, y + h - 0.50, stage_name, ha="left",
                fontsize=11, fontweight="bold", color=banner_color)
        ax.text(x + 0.3, y + 0.35, host, ha="left",
                fontsize=7.5, color="#666", style="italic")
        ax.plot([x + 3.4, x + 3.4], [y + 0.15, y + h - 0.15],
                color=banner_color, linewidth=0.6, alpha=0.4)
        ax.text(x + 3.6, y + h - 0.50, artifact, ha="left", fontsize=9,
                color="#222", fontweight="bold")
        ax.text(x + 3.6, y + 0.35, tools, ha="left", fontsize=7.5,
                color="#555")
        ax.plot([x + 8.4, x + 8.4], [y + 0.15, y + h - 0.15],
                color=banner_color, linewidth=0.6, alpha=0.4)
        ax.text(x + 8.6, y + h / 2, gate, ha="left", va="center",
                fontsize=7.0, color="#2a7d2e", style="italic",
                fontweight="bold", linespacing=1.3)

    def arrow_down(x_center, y_top, y_bot):
        ax.add_patch(FancyArrowPatch(
            (x_center, y_top), (x_center, y_bot),
            arrowstyle="-|>", mutation_scale=14,
            linewidth=1.4, color="#3a6da6",
        ))

    stages = [
        ("Windows + CUDA 12.8",   "1. Train",
         "PyTorch checkpoint",
         "AMP fp16 + ArcFace curriculum\n(m: 0.3 -> 0.5)",
         "20.4 M synth samples · 20 epochs",
         "#fff1d6", "#a4413f"),
        ("Windows + CUDA 12.8",   "2. Port",
         "Keras FP32 model (5 outputs)",
         "PyTorch -> Keras hand-port\n+ stride-2 padding-parity fix",
         "max-abs-diff < 1e-5 vs PT  OK",
         "#e6f0fa", "#3a6da6"),
        ("Windows + TF 2.15",     "3. Quantize",
         "TFLite INT8 (11.5 MB)",
         "Keras -> TFLite INT8 PTQ\n+ 300-sample MinMax calibration",
         "PT vs INT8: 0.00 pp loss  OK",
         "#e6f0fa", "#3a6da6"),
        ("WSL Ubuntu 22.04",      "4. Compile",
         "Edge TPU TFLite",
         "edgetpu_compiler -s, v16.0\n(Linux-only tool)",
         "41 / 41 ops · 7.58 MiB on-chip  OK",
         "#fff5e1", "#cc8a1a"),
        ("Pi 5 + Coral USB",      "5. Deploy",
         "Pi inference (live)",
         "ai-edge-litert + libedgetpu1-std\n+ demo wrappers",
         "24.7 ms / char · 81.6 % top-1  OK",
         "#dff3e0", "#2a7d2e"),
    ]

    n = len(stages)
    top = 11.5
    pitch = 2.1
    for i, st in enumerate(stages):
        y = top - i * pitch
        stage(y, *st)
        if i < n - 1:
            arrow_down(7.0, y - 0.05, y - 0.4)

    ax.text(7.0, 0.35,
            "Each arrow is a numerical-parity / accuracy / op-coverage gate.  "
            "End-to-end accuracy preserved at 0.00 pp loss.",
            ha="center", fontsize=8.5, style="italic", color="#444")

    fig.savefig(OUT / "fig3_deploy_pipeline.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig3_deploy_pipeline.png")


# =============================================================================
# Figure 4 — Pareto frontier (latency × accuracy × size)
# =============================================================================

def fig4_pareto():
    engines = [
        # (name,                lat_ms, top1_pct, size_mb, color, ours)
        ("Tesseract",            982,    36.8,    50,    "#888888", False),
        ("EasyOCR ja",           64,     52.6,    70,    "#888888", False),
        ("EasyOCR ch_tra",       464,    65.8,    70,    "#888888", False),
        ("EasyOCR ch_sim",       63,     36.8,    70,    "#888888", False),
        ("cnocr",                12.7,   50.0,    100,   "#888888", False),
        ("Manga-OCR",            788,    65.8,    440,   "#888888", False),
        ("SCER (CPU)",           28.5,   81.6,    11,    "#2a7d2e", True),
        ("SCER (Coral)",         24.7,   81.6,    11,    "#2a7d2e", True),
    ]

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    label_offsets = {
        "Tesseract":          (-60, -16),
        "EasyOCR ja":         (10, -12),
        "EasyOCR ch_tra":     (-25, 14),
        "EasyOCR ch_sim":     (10, -12),
        "cnocr":              (12, -14),
        "Manga-OCR":          (10, -16),
        "SCER (CPU)":         (-60, 10),
        "SCER (Coral)":       (10, -12),
    }
    for name, lat, acc, size, color, ours in engines:
        s = max(80, np.sqrt(size) * 38)
        ax.scatter(lat, acc, s=s, color=color, alpha=0.55,
                   edgecolor="black", linewidth=0.8 if not ours else 2.0,
                   zorder=3 if ours else 2)
        offset = label_offsets.get(name, (10, 6))
        ax.annotate(name, xy=(lat, acc),
                    xytext=offset, textcoords="offset points",
                    fontsize=8,
                    fontweight="bold" if ours else "normal",
                    color="#222")

    ax.set_xscale("log")
    ax.set_xlim(6, 2000)
    ax.set_ylim(25, 95)
    ax.set_xlabel("Pi 5 end-to-end latency per character (ms, log scale)")
    ax.set_ylabel("Top-1 accuracy on 38-image CJK test set (%)")
    ax.set_title("Latency-Accuracy Pareto Frontier", fontsize=11, pad=10)
    ax.grid(alpha=0.25, linestyle=":")

    ax.plot([12.7, 24.7], [50.0, 81.6], "--", color="#2a7d2e", alpha=0.5,
            linewidth=1.2, label="Pareto frontier")

    legend_elems = [
        Line2D([0], [0], marker="o", color="w", label="this work",
               markerfacecolor="#2a7d2e", markersize=11,
               markeredgecolor="black", markeredgewidth=1.4),
        Line2D([0], [0], marker="o", color="w", label="commodity OCR",
               markerfacecolor="#888888", markersize=11,
               markeredgecolor="black", markeredgewidth=0.6),
    ]
    ax.legend(handles=legend_elems, loc="lower right", framealpha=0.95)

    ax.text(8, 90, "<- faster\n^ more accurate\nv smaller bubble = better",
            fontsize=7, color="#444",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#f5f5f5", edgecolor="#bbb"))

    plt.tight_layout()
    fig.savefig(OUT / "fig4_pareto.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig4_pareto.png")


# =============================================================================
# Figure 5 — Coral SRAM utilization (cache split)
# =============================================================================

def fig5_coral_cache():
    fig, ax = plt.subplots(figsize=(6.5, 3.8))

    models = ["Baseline\n(98K-FC INT8)", "SCER\n(emb head INT8)"]
    on_chip = [7.59, 7.58]
    off_chip = [51.43, 3.41]
    totals = [a + b for a, b in zip(on_chip, off_chip)]

    x = np.arange(len(models))
    bw = 0.55

    ax.bar(x, on_chip, bw, label="On-chip cache (<= 8 MiB SRAM)",
           color="#2a7d2e", edgecolor="black", linewidth=0.8)
    ax.bar(x, off_chip, bw, bottom=on_chip,
           label="Off-chip stream (USB)",
           color="#cc4a3f", edgecolor="black", linewidth=0.8)

    ax.axhline(y=8.0, linestyle="--", linewidth=1.2, color="#444",
               alpha=0.7)
    ax.text(1.55, 8.0, " 8 MiB Coral SRAM ceiling",
            fontsize=8, color="#444", ha="left", va="center",
            backgroundcolor="white")

    annotations = [
        ("59 MB total\n13 % cached on-chip\n-> Coral ~ CPU (no speedup)",
         totals[0], "#a4413f"),
        ("11 MB total\n69 % cached on-chip\n-> Coral -13 % latency vs CPU",
         totals[1], "#2a7d2e"),
    ]
    for i, (txt, top, color) in enumerate(annotations):
        ax.text(i, top + 2.5, txt, ha="center", fontsize=8,
                fontweight="bold", color=color, linespacing=1.3)

    for i in range(2):
        ax.text(i, on_chip[i] / 2, f"{on_chip[i]:.1f} MB",
                ha="center", va="center", color="white",
                fontsize=8, fontweight="bold")
        if off_chip[i] >= 8:
            ax.text(i, on_chip[i] + off_chip[i] / 2, f"{off_chip[i]:.1f} MB",
                    ha="center", va="center", color="white",
                    fontsize=8, fontweight="bold")
        else:
            ax.annotate(
                f"{off_chip[i]:.1f} MB",
                xy=(i, on_chip[i] + off_chip[i] / 2),
                xytext=(i + 0.4, on_chip[i] + off_chip[i] / 2 + 1.5),
                fontsize=8, fontweight="bold", color="#cc4a3f",
                arrowprops=dict(arrowstyle="-", color="#cc4a3f",
                                lw=0.8),
            )

    ax.set_ylabel("Model weight size (MiB)")
    ax.set_xticks(x); ax.set_xticklabels(models)
    ax.set_xlim(-0.6, 1.95)
    ax.set_ylim(0, 70)
    ax.set_title("Coral SRAM Cache Split", fontsize=11, pad=10)
    ax.legend(loc="upper right", framealpha=0.95)
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    fig.savefig(OUT / "fig5_coral_cache.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig5_coral_cache.png")


# =============================================================================
# Figure 6 — Training curve (two-wave cluster crystallization)
# =============================================================================

def fig6_training_curve():
    epochs = list(range(1, 21))
    emb_top1 = [
        2.0, 6.0, 11.0, 17.0, 22.0, 26.0, 30.0, 33.0, 35.0, 37.5,
        78.3, 80.6, 79.4, 78.5, 78.5, 79.9, 82.9, 89.9, 94.5, 95.2,
    ]

    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.plot(epochs, emb_top1, "-o", color="#3a6da6", linewidth=1.5,
            markersize=4, markerfacecolor="white", markeredgewidth=1.2)

    # Wave 1 highlight: epoch 10 -> 11 (red arrow on the data jump)
    ax.annotate("", xy=(11, emb_top1[10]), xytext=(10, emb_top1[9]),
                arrowprops=dict(arrowstyle="->", color="#cc4a3f",
                                linewidth=2.5))
    ax.text(11.4, 56,
            "Wave 1\n+40.8 pp in 1 epoch\n(lr reset @ m=0.5 boundary)",
            fontsize=8, color="#cc4a3f", fontweight="bold")

    # Wave 2 highlight — taller/wider rectangle so the inside label fits
    # without touching the border, and the label text sits clear of the
    # data line.
    ax.add_patch(Rectangle((16.3, 78), 4.0, 21,
                            linewidth=1.5, edgecolor="#cc4a3f",
                            facecolor="#fde2e1", alpha=0.35))
    ax.text(18.3, 70,
            "Wave 2\n+12 pp on cosine-LR tail\n(metric crystallization)",
            ha="center", fontsize=8, color="#cc4a3f", fontweight="bold")

    # Phase shading
    ax.axvspan(0.5, 10.5, color="#e6f0fa", alpha=0.4, zorder=0)
    ax.axvspan(10.5, 20.5, color="#dff3e0", alpha=0.4, zorder=0)
    ax.text(5.5, 5, "First stage (epochs 1-10)", ha="center", fontsize=8,
            color="#3a6da6", style="italic")
    ax.text(15.5, 5, "Extension stage (epochs 11-20)",
            ha="center", fontsize=8, color="#2a7d2e", style="italic")

    ax.set_xlabel("Epoch")
    ax.set_ylabel("Embedding top-1 accuracy on 12K val set (%)")
    ax.set_title("ArcFace Training Curve", fontsize=11, pad=10)
    ax.set_xlim(0, 21); ax.set_ylim(0, 100)
    ax.set_xticks(range(0, 21, 2))
    ax.grid(alpha=0.25, linestyle=":")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    fig.savefig(OUT / "fig6_training_curve.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig6_training_curve.png")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(f"Generating figures -> {OUT}")
    fig1_head_comparison()
    fig2_scer_full()
    fig3_deploy_pipeline()
    fig4_pareto()
    fig5_coral_cache()
    fig6_training_curve()
    print("done.")
