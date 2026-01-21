"""Anomalib Padim の学習・検証を行う小さなエントリポイント。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from anomalib.data import get_datamodule  # type: ignore[import]
from anomalib.models import get_model  # type: ignore[import]
from omegaconf import DictConfig, OmegaConf  # type: ignore[import]

from anomalib.trainers import get_trainer  # type: ignore[import]

LOGGER = logging.getLogger("demo_anomalib.padim")


def resolve_paths(config_path: Path, output: Path, config: DictConfig) -> None:
    """Normalize dataset/output paths. Dataset path is specified in config.yaml."""
    # Ensure class_path/init_args structure exists first
    ensure_data_class_path(config)

    # Ensure dataset exists at the path specified in config
    if "init_args" in config.data and "root" in config.data.init_args:
        dataset_root = Path(config.data.init_args.root)
        _ensure_dataset_exists(dataset_root)

    output_path = output.expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    config.trainer.default_root_dir = str(output_path)

    resolved_config_path = output_path / "resolved_config.yaml"
    OmegaConf.save(config, resolved_config_path)
    LOGGER.info("Resolved config saved to %s", resolved_config_path)


def ensure_data_class_path(config: DictConfig) -> None:
    """Ensure data.class_path/init_args exist for anomalib>=1.1 style configs."""
    if "class_path" in config.data:
        return

    dataset_name = str(config.data.get("name", "cifar10")).lower()
    mapping = {
        "cifar10": "anomalib.data.cifar10.CIFAR10",
        "visa": "anomalib.data.Folder",  # Updated for anomalib v2.x
    }
    if dataset_name not in mapping:
        raise ValueError(
            f"data.name={dataset_name} に対応する class_path が未指定です。"
            "config.data.class_path を明示してください。"
        )

    class_path = mapping[dataset_name]
    init_args = {}
    for key, value in config.data.items():
        if key in {"class_path", "init_args", "name"}:
            continue
        init_args[key] = value

    # For folder-based datasets, map 'path' to 'root'
    if dataset_name == "visa":
        if "path" in init_args:
            init_args["root"] = init_args.pop("path")
    elif dataset_name == "cifar10":
        # anomalib CIFAR10 expects 'root' instead of 'path'
        if "path" in init_args:
            init_args["root"] = init_args.pop("path")

    config.data.class_path = class_path
    config.data.init_args = init_args


def _ensure_dataset_exists(dataset_root: Path) -> None:
    """Check if dataset exists at the expected location."""
    if not dataset_root.exists():
        raise RuntimeError(
            f"データセットが見つかりません。{dataset_root} に事前に配置してください。"
        )


def run_training(config: DictConfig, output_dir: Path) -> None:
    """Train and evaluate the Padim model defined in the config."""
    # 1. データモジュール、モデル、トレーナーを取得
    LOGGER.info("Loading datamodule, model, and trainer")
    datamodule = get_datamodule(config.data)
    model = get_model(config.model)
    trainer = get_trainer(config)

    # 2. 学習を実行
    LOGGER.info("Starting training")
    trainer.fit(model=model, datamodule=datamodule)

    # 3. テストデータで評価
    LOGGER.info("Evaluating on test data")
    test_results = trainer.test(model=model, datamodule=datamodule)

    # 4. メトリクスを抽出（anomalib 2.2.0 では test_results に含まれる）
    metrics = {}
    if test_results and len(test_results) > 0:
        for key, value in test_results[0].items():
            if isinstance(value, (int, float)):
                metrics[key] = float(value)
            elif hasattr(value, 'item'):
                try:
                    metrics[key] = float(value.item())
                except (ValueError, TypeError):
                    pass

    LOGGER.info(f"Extracted metrics: {metrics}")

    # 5. metrics.json を保存
    metrics_data = {
        "params": {
            "method": config.model.class_path.split(".")[-1].lower(),
            "backbone": str(config.model.init_args.get("backbone", "resnet18")),
            "dataset": config.data.init_args.get("name", "unknown"),
            "image_size": str(config.data.init_args.get("image_size", "default")),
            "max_epochs": str(config.trainer.get("max_epochs", 2)),
        },
        "metrics": metrics,
    }

    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_data, f, indent=2)
    LOGGER.info(f"Metrics saved to {metrics_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Anomalib Padim demo runner.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("LeadersBoard/demo_anomalib/config.yaml"),
        help="Padim 用の設定ファイル",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="ログやチェックポイントを出力するディレクトリ",
    )
    args = parser.parse_args()

    # ログファイルを設定
    log_file = args.output / "training.log"
    args.output.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    config = OmegaConf.load(args.config)
    resolve_paths(args.config, args.output, config)
    run_training(config, args.output)

    LOGGER.info(f"Training log saved to {log_file}")


if __name__ == "__main__":
    main()
