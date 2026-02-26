"""投稿コード向け可視化アーティファクト生成ユーティリティ。

Worker の VisualizationCollector が期待するファイル命名規則に従い、
trainer.predict() の結果から可視化画像と CSV を生成する。

出力:
  visualizations/{image_name}_original.png
  visualizations/{image_name}_heatmap.png
  visualizations/{image_name}_mask.png
  visualizations/{image_name}_overlay.png
  image_predictions.csv
  pixel_predictions.csv
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import cv2  # type: ignore[import]
import numpy as np  # type: ignore[import]
import torch  # type: ignore[import]
from PIL import Image  # type: ignore[import]

logger = logging.getLogger(__name__)


# ===================================================================
# Public API
# ===================================================================


def save_visualization_artifacts(
    model: Any,
    datamodule: Any,
    trainer: Any,
    output_dir: Path,
) -> None:
    """可視化アーティファクトを生成する。

    失敗してもメトリクス記録を妨げないようエラーを握りつぶす。
    """
    try:
        _generate(model, datamodule, trainer, output_dir)
    except Exception as exc:
        logger.warning("Visualization generation failed (non-blocking): %s", exc)


# ===================================================================
# Internal implementation
# ===================================================================


def _generate(
    model: Any,
    datamodule: Any,
    trainer: Any,
    output_dir: Path,
) -> None:
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Running prediction for visualization artifacts")
    predictions = trainer.predict(model=model, datamodule=datamodule)
    if not predictions:
        logger.warning("No predictions returned, skipping visualization")
        return

    image_rows: list[dict[str, Any]] = []
    pixel_rows: list[dict[str, Any]] = []
    count = 0

    for batch in predictions:
        images = _field(batch, "image")
        anomaly_maps = _field(batch, "anomaly_map")
        pred_masks = _field(batch, "pred_mask")
        pred_scores = _field(batch, "pred_score")
        pred_labels = _field(batch, "pred_label")
        image_paths = _field(batch, "image_path")

        batch_size = _batch_len(image_paths, anomaly_maps, pred_masks)
        for i in range(batch_size):
            img_name = (
                Path(image_paths[i]).stem
                if image_paths is not None and i < len(image_paths)
                else f"image_{count:04d}"
            )

            img = _at(images, i)
            amap = _at(anomaly_maps, i)
            mask = _at(pred_masks, i)

            if img is not None:
                _save_denormalized(img, viz_dir / f"{img_name}_original.png")
            else:
                logger.warning("No image tensor for: %s", img_name)

            if amap is not None:
                _save_heatmap(amap, viz_dir / f"{img_name}_heatmap.png")

            if mask is not None:
                _save_mask(mask, viz_dir / f"{img_name}_mask.png")

            if img is not None and amap is not None:
                _save_overlay(img, amap, viz_dir / f"{img_name}_overlay.png")

            score = _scalar(pred_scores, i, 0.0)
            label = _scalar(pred_labels, i, "unknown")
            path_str = (
                str(image_paths[i])
                if image_paths is not None and i < len(image_paths)
                else img_name
            )
            image_rows.append(
                {
                    "image_path": path_str,
                    "anomaly_score": float(score),
                    "pred_label": str(label),
                }
            )
            if amap is not None:
                pixel_rows.append(
                    {
                        "image_path": path_str,
                        "height": int(amap.shape[-2]),
                        "width": int(amap.shape[-1]),
                        "anomaly_map_path": f"visualizations/{img_name}_heatmap.png",
                    }
                )

            count += 1

    _write_csv(
        output_dir / "image_predictions.csv",
        image_rows,
        ["image_path", "anomaly_score", "pred_label"],
    )
    _write_csv(
        output_dir / "pixel_predictions.csv",
        pixel_rows,
        ["image_path", "height", "width", "anomaly_map_path"],
    )
    logger.info("Generated %d visualization artifact sets", count)


# ===================================================================
# Batch / tensor access helpers
# ===================================================================


def _field(batch: Any, name: str) -> Any:
    return batch.get(name) if isinstance(batch, dict) else getattr(batch, name, None)


def _batch_len(*fields: Any) -> int:
    for f in fields:
        if f is None:
            continue
        if hasattr(f, "shape") and len(f.shape) > 0:
            return int(f.shape[0])
        if isinstance(f, (list, tuple)):
            return len(f)
    return 0


def _at(tensor: Any, idx: int) -> Any:
    if tensor is None:
        return None
    try:
        return tensor[idx]
    except (IndexError, TypeError, KeyError):
        return None


def _scalar(field: Any, idx: int, default: Any = 0.0) -> Any:
    if field is None:
        return default
    try:
        val = field[idx]
        return val.item() if hasattr(val, "item") else val
    except (IndexError, TypeError, KeyError):
        return default


# ===================================================================
# Image saving helpers
# ===================================================================


IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _denormalize(tensor: Any) -> np.ndarray:
    """ImageNet 正規化済み [C,H,W] テンソルを [H,W,3] uint8 に逆変換する。"""
    arr = tensor.detach().cpu().float().numpy()
    if arr.ndim == 3 and arr.shape[0] in (1, 3):
        arr = np.transpose(arr, (1, 2, 0))
    if arr.ndim == 2:
        arr = arr[:, :, np.newaxis]
    if arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)
    arr = arr * IMAGENET_STD + IMAGENET_MEAN
    return np.clip(arr * 255, 0, 255).astype(np.uint8)


def _normalize_map(tensor: Any) -> np.ndarray:
    """異常マップテンソルを [0, 255] uint8 に正規化する。"""
    arr = tensor.detach().cpu().float().squeeze().numpy()
    lo, hi = float(arr.min()), float(arr.max())
    if hi > lo:
        arr = (arr - lo) / (hi - lo)
    else:
        arr = np.zeros_like(arr)
    return (arr * 255).astype(np.uint8)


def _save_denormalized(tensor: Any, path: Path) -> None:
    """前処理後の画像テンソルを逆正規化して保存する。"""
    arr = _denormalize(tensor)
    logger.info(
        "Original (denorm): shape=%s, range=[%d, %d]", arr.shape, int(arr.min()), int(arr.max())
    )
    Image.fromarray(arr).save(path)


def _save_heatmap(amap: Any, path: Path) -> None:
    gray = _normalize_map(amap)
    colored = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    Image.fromarray(cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)).save(path)


def _save_mask(mask: Any, path: Path) -> None:
    arr = mask.detach().cpu().squeeze()
    if arr.dtype == torch.bool:
        np_arr = arr.numpy().astype(np.uint8) * 255
    else:
        farr = arr.float().numpy()
        lo, hi = float(farr.min()), float(farr.max())
        if hi > lo:
            farr = (farr - lo) / (hi - lo) * 255.0
        else:
            farr = farr * 255.0
        np_arr = np.clip(farr, 0, 255).astype(np.uint8)
    logger.info(
        "Mask: shape=%s nonzero=%d/%d",
        np_arr.shape,
        int(np.count_nonzero(np_arr)),
        np_arr.size,
    )
    Image.fromarray(np_arr, mode="L").save(path)


def _save_overlay(
    img_tensor: Any,
    amap: Any,
    path: Path,
    alpha: float = 0.4,
) -> None:
    """前処理後の画像テンソルとヒートマップを重ね合わせて保存する。"""
    img_arr = _denormalize(img_tensor)
    gray = _normalize_map(amap)
    heat = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    if heat_rgb.shape[:2] != img_arr.shape[:2]:
        heat_rgb = cv2.resize(heat_rgb, (img_arr.shape[1], img_arr.shape[0]))
    blended = cv2.addWeighted(img_arr, 1 - alpha, heat_rgb, alpha, 0)
    Image.fromarray(blended).save(path)


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str],
) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Saved %s (%d rows)", path.name, len(rows))
