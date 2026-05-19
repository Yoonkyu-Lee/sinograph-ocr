"""Export the trained SCER model to ONNX for in-app (Rust / tract) inference.

doc/39 M0. The desktop app (`sinograph_explorer`) runs hanzi recognition in
Rust via the `tract-onnx` crate, so the PyTorch checkpoint must be exported
to ONNX. Only the 128-d embedding is needed at inference time, so a thin
wrapper exposes a single output: `embedding`.

The exported ONNX must be paired at deploy time with the anchor DB built
from the SAME checkpoint — `deploy_pi/export/scer_anchor_db_v20.npy`
(epoch-20 best.pt, emb/top1 0.952). This script verifies that pairing.

Usage (Windows venv):
    .venv/Scripts/python.exe train_engine_v4/scripts/52_export_scer_onnx.py \
        --ckpt   train_engine_v4/out/16_scer_v1/best.pt \
        --anchor deploy_pi/export/scer_anchor_db_v20.npy \
        --class-index deploy_pi/export/class_index.json \
        --test   deploy_pi/test_chars \
        --out    deploy_pi/export/scer_v4.onnx
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "train_engine_v4"))

from modules.model import build_scer  # noqa: E402

INPUT_SIZE = 128
N_CLASS = 98169
EMB_DIM = 128
OPSET = 13


def log(msg: str) -> None:
    print(msg, flush=True)


class EmbeddingWrapper(nn.Module):
    """Wraps SCERModel so forward(x) returns only the L2-normalized embedding.

    A single-output graph is the cleanest target for tract: no dict, no
    unused structure heads.
    """

    def __init__(self, scer: nn.Module):
        super().__init__()
        self.scer = scer

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.scer.forward_inference(x)["embedding"]


def preprocess(img_path: Path) -> np.ndarray:
    """RGB -> pad-to-square (white) -> resize bilinear -> [-1,1] -> NCHW.

    Matches deploy_pi/infer_pi_onnx.py:preprocess exactly.
    """
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    side = max(w, h)
    canvas = Image.new("RGB", (side, side), color=(255, 255, 255))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2))
    canvas = canvas.resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    arr = np.asarray(canvas, dtype=np.float32) / 255.0
    arr = (arr - 0.5) / 0.5
    arr = np.transpose(arr, (2, 0, 1))
    return np.expand_dims(arr, 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="train_engine_v4/out/16_scer_v1/best.pt")
    ap.add_argument("--anchor", default="deploy_pi/export/scer_anchor_db_v20.npy")
    ap.add_argument("--class-index", default="deploy_pi/export/class_index.json")
    ap.add_argument("--test", default="deploy_pi/test_chars")
    ap.add_argument("--out", default="deploy_pi/export/scer_v4.onnx")
    args = ap.parse_args()

    ckpt_path = (REPO / args.ckpt).resolve()
    out_path = (REPO / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- build model + load checkpoint ----
    log(f"[52] loading checkpoint: {ckpt_path}")
    ck = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    state = ck["model"] if "model" in ck else ck
    state = {k.removeprefix("_orig_mod."): v for k, v in state.items()}
    log(f"[52] checkpoint epoch={ck.get('epoch')} "
        f"best={ck.get('best_metric_key')}={ck.get('best_metric_value')}")

    model = build_scer("resnet18", num_classes=N_CLASS, emb_dim=EMB_DIM)
    msg = model.load_state_dict(state, strict=False)
    # Missing keys are acceptable ONLY for training-only modules.
    bad_missing = [k for k in msg.missing_keys
                   if not k.startswith(("char_head.", "arc_classifier."))]
    if bad_missing:
        raise RuntimeError(f"unexpected missing keys: {bad_missing[:10]}")
    if msg.unexpected_keys:
        raise RuntimeError(f"unexpected keys in ckpt: {msg.unexpected_keys[:10]}")
    log(f"[52] state loaded — {len(msg.missing_keys)} missing keys "
        f"(char_head/arc_classifier only, as expected)")
    model.eval()

    wrapper = EmbeddingWrapper(model).eval()

    # ---- export ----
    dummy = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE)
    log(f"[52] exporting ONNX (opset {OPSET}, fixed batch 1) -> {out_path}")
    # dynamo=False -> legacy TorchScript exporter: no onnxscript dependency,
    # well-tested for ResNet-18, and produces a clean opset-13 graph for tract.
    torch.onnx.export(
        wrapper, dummy, str(out_path),
        input_names=["input"], output_names=["embedding"],
        opset_version=OPSET, do_constant_folding=True, dynamo=False,
    )
    log(f"[52] wrote {out_path}  ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # ---- verification ----
    import json
    anchors = np.load(str((REPO / args.anchor).resolve())).astype(np.float32)
    log(f"[52] anchor DB: {anchors.shape}")
    class_index = json.load(open((REPO / args.class_index).resolve(),
                                  encoding="utf-8"))
    idx_to_key = {v: k for k, v in class_index.items()}

    def key_to_char(k: str) -> str:
        try:
            return chr(int(k[2:], 16))
        except Exception:
            return "?"

    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(out_path),
                                    providers=["CPUExecutionProvider"])
        have_ort = True
    except ImportError:
        log("[52] WARN: onnxruntime not installed — ONNX numeric check skipped, "
            "using torch embeddings for the NN gate")
        have_ort = False

    test_dir = (REPO / args.test).resolve()
    paths = sorted(test_dir.glob("*.png"))
    log(f"[52] verifying on {len(paths)} test images from {test_dir}\n")

    top1 = top5 = 0
    max_onnx_diff = 0.0
    for path in paths:
        gt = path.stem
        arr = preprocess(path)

        with torch.no_grad():
            emb_torch = wrapper(torch.from_numpy(arr)).numpy()[0]

        if have_ort:
            emb_onnx = sess.run(None, {"input": arr})[0][0]
            diff = float(np.abs(emb_torch - emb_onnx).max())
            max_onnx_diff = max(max_onnx_diff, diff)
            emb = emb_onnx
        else:
            emb = emb_torch

        emb = emb / max(np.linalg.norm(emb), 1e-8)
        sims = anchors @ emb
        order = np.argsort(-sims)[:5]
        cands = [key_to_char(idx_to_key[int(i)]) for i in order]
        hit1 = cands[0] == gt
        hit5 = gt in cands
        top1 += hit1
        top5 += hit5
        mark = "OK " if hit1 else ("o5 " if hit5 else "XX ")
        log(f"  {mark} gt={gt}  top5={' '.join(cands)}  sim={sims[order[0]]:.3f}")

    n = len(paths)
    log("")
    log("=" * 60)
    log(f"[52] GATE M0 — {n} images")
    log(f"  top-1: {top1}/{n}  ({100*top1/n:.1f}%)")
    log(f"  top-5: {top5}/{n}  ({100*top5/n:.1f}%)")
    if have_ort:
        log(f"  max |torch - onnx| embedding diff: {max_onnx_diff:.2e}")
        if max_onnx_diff > 1e-3:
            raise RuntimeError(f"ONNX output diverges from torch "
                               f"({max_onnx_diff:.2e}) — export is wrong")
    if top1 < int(0.6 * n):
        raise RuntimeError(f"GATE M0 FAIL — top-1 {top1}/{n} too low; "
                           f"check ckpt/anchor pairing")
    log("[52] GATE M0 PASS")


if __name__ == "__main__":
    main()
