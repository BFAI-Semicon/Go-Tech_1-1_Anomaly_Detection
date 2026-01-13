# LeadersBoard 投稿者ガイド

LeadersBoard へようこそ！このプラットフォームでは、あなたの機械学習モデルを投稿し、標準データセットで評価することができます。

## 目次

- [はじめに](#はじめに)
- [投稿の流れ](#投稿の流れ)
- [投稿方法](#投稿方法)
- [結果の確認](#結果の確認)
- [投稿ルール](#投稿ルール)
- [サンプルコード](#サンプルコード)
- [FAQ](#faq)

## はじめに

### LeadersBoard とは

LeadersBoard は、機械学習モデルの性能を公平に比較するためのプラットフォームです。あなたのモデルを投稿すると、自動的に評価が実行され、結果がリーダーボードに表示されます。

### 必要なもの

- **API Token**: 管理者から発行されたトークン
- **投稿ファイル**:
  - `main.py`: モデルの学習・評価を実行するPythonスクリプト
  - `config.yaml`: モデルの設定ファイル
  - `dataset.zip`: データセットファイル（zipファイルとして含める）
  - その他必要なファイル（オプション）

#### データセットについて

- データセットは**zipファイル**として投稿に含める必要があります
- 例: `pcb1.zip` をアップロードすると、`main.py` 実行時に自動展開されます
- `config.yaml` の `root` パラメータは展開後のパスを指定します

  ```yaml
  # 例: pcb1.zip → pcb1/Data/Images/
  root: pcb1/Data/Images
  ```

## 投稿の流れ

```text
1. ファイルを準備（main.py, config.yaml）
   ↓
2. Web UI から投稿
   ↓
3. ジョブが自動実行（GPU環境）
   ↓
4. metrics.json が生成され、MLflow に自動記録
   ↓
5. MLflow UI で結果を確認
   ↓
6. リーダーボードでランキング確認
```

## 投稿方法

### Web UI から投稿

1. ブラウザで `http://<hostname>:8501` にアクセス
2. **API Token** を入力（管理者から受け取ったトークン）
3. **ファイルをアップロード**:
   - `main.py`: エントリポイント
   - `config.yaml`: 設定ファイル
   - その他必要なファイル
4. **Entrypoint** に `main.py` を指定
5. **Config File** に `config.yaml` を指定
6. **Metadata (JSON)** に追加情報を入力（オプション）:

   ```json
   {
     "method": "padim",
     "description": "ResNet18ベースのPADIMモデル"
   }
   ```

7. **Submit** ボタンをクリック
8. ジョブ一覧で進捗を確認（5秒ごとに自動更新）

### ステータスの見方

- ⏳ **pending**: ジョブが待機中
- ⏳ **running**: ジョブが実行中
- ✅ **completed**: ジョブが正常に完了
- ❌ **failed**: ジョブが失敗（ログを確認してください）

## 結果の確認

### MLflow UI でメトリクスを確認

1. ブラウザで `http://<hostname>:5010` にアクセス
2. 実験一覧から自分の実験を選択
3. メトリクス（AUROC、F1スコアなど）を確認
4. アーティファクト（画像、モデルファイルなど）をダウンロード

### リーダーボードでランキング確認

1. MLflow UI の「Compare」機能を使用
2. 複数の実験を選択して比較
3. メトリクスでソートしてランキングを確認

## 投稿ルール

### レート制限

投稿には以下の制限があります：

- **1時間あたりの投稿数**: 最大50回（デフォルト）
- **同時実行ジョブ数**: 最大2個（デフォルト）

※ 実際の制限値は管理者の設定により異なる場合があります。制限を超えると、エラーメッセージが表示されます。

### ファイル要件

#### `main.py` の要件

- **必須関数**: `main()` 関数を実装
- **出力ファイル**: `--output` で指定されたディレクトリに `metrics.json` を生成
- **metrics.json 形式**: `params` と `metrics` を含むJSON形式
- **エラーハンドリング**: 例外が発生した場合は適切にログ出力

#### `config.yaml` の要件

- **YAML形式**: 有効なYAML構文
- **必須フィールド**: モデル、データ、学習設定を含む
- **サンプル**: 後述の「サンプルコード」を参照

### 評価基準

投稿されたモデルは以下の基準で評価されます：

- **AUROC** (Area Under ROC Curve): 異常検知性能の主要指標
- **F1スコア**: 精度と再現率のバランス
- **実行時間**: 学習・評価にかかった時間（MLflowが自動記録）
- **その他**: `metrics.json` に含めたカスタムメトリクス（オプション）

## サンプルコード

### `config.yaml`

```yaml
model:
  class_path: anomalib.models.Padim
  init_args:
    backbone: resnet18
    layers:
      - layer1
      - layer2
      - layer3

data:
  name: visa
  class_path: anomalib.data.Folder
  init_args:
    name: pcb1
    root: pcb1/Data/Images # zipファイル展開後のパス
    normal_dir: Normal
    abnormal_dir: Anomaly
    extensions: # オプション: 省略時はデフォルト画像形式を使用
      - .jpg
      - .jpeg
      - .JPG # 大文字拡張子も必要な場合は明示
      - .JPEG
      - .png
      - .PNG
    train_batch_size: 32
    eval_batch_size: 32
    num_workers: 0

trainer:
  max_epochs: 10
  accelerator: gpu
  devices: 1

metrics:
  - auroc
  - f1_score
```

### `main.py` の例

```python
import argparse
import json
import logging
import zipfile
from pathlib import Path
from omegaconf import OmegaConf
from anomalib.data import get_datamodule
from anomalib.models import get_model
from anomalib.trainers import get_trainer

def extract_dataset_if_needed(config_path: Path):
    """
    データセットがzipファイルで提供されている場合に自動展開
    例: pcb1.zip → pcb1/
    """
    base_dir = config_path.parent

    # 一般的なデータセット名のzipファイルを検索
    for zip_file in base_dir.glob("*.zip"):
        dataset_dir = base_dir / zip_file.stem
        if not dataset_dir.exists():
            logging.info(f"Extracting {zip_file.name}...")
            with zipfile.ZipFile(zip_file) as archive:
                archive.extractall(base_dir)
            logging.info(f"Extracted to {dataset_dir}")

def main():
    """
    カスタムメトリクスとパラメータを含む投稿例
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    # 出力ディレクトリを作成
    args.output.mkdir(parents=True, exist_ok=True)

    # ログファイルを設定
    log_file = args.output / "training.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # データセットをzipから展開（必要な場合）
    extract_dataset_if_needed(args.config)

    # 設定ファイルを読み込み
    config = OmegaConf.load(args.config)
    config.trainer.default_root_dir = str(args.output)

    try:
        # データモジュール、モデル、トレーナーを取得
        logger.info("Loading datamodule, model, and trainer")
        datamodule = get_datamodule(config.data)
        model = get_model(config.model)
        trainer = get_trainer(config)

        # 学習
        logger.info("Starting training...")
        trainer.fit(model=model, datamodule=datamodule)

        # 評価
        logger.info("Starting evaluation...")
        test_results = trainer.test(model=model, datamodule=datamodule)

        # メトリクスを抽出
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

        # metrics.json を生成
        metrics_data = {
            "params": {
                "method": config.model.class_path.split(".")[-1].lower(),
                "backbone": str(config.model.init_args.get("backbone", "resnet18")),
                "dataset": config.data.init_args.get("name", "unknown"),
                "image_size": str(config.data.init_args.get("image_size", "default")),
                "max_epochs": str(config.trainer.get("max_epochs", 10))
            },
            "metrics": metrics
        }

        metrics_path = args.output / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics_data, f, indent=2)

        logger.info(f"Training completed successfully!")
        logger.info(f"Metrics saved to {metrics_path}")
        logger.info(f"Training log saved to {log_file}")
        logger.info(f"Results: {metrics}")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise

if __name__ == "__main__":
    main()
```

## FAQ

### Q1: API Token はどこで取得できますか？

**A**: プラットフォーム管理者に問い合わせてください。トークンは個人に紐づいており、他人と共有しないでください。

### Q2: ジョブが失敗しました。どうすればいいですか？

**A**: 以下の手順で原因を特定してください：

1. Web UI の「Show logs」ボタンでログを確認
2. エラーメッセージを確認
3. `main.py` と `config.yaml` の構文をチェック
4. サンプルコードと比較して修正

### Q3: どのデータセットが使えますか？

**A**: 現在サポートされているデータセット：

- **VisA**: 産業用異常検知データセット
- **MVTec AD**: テクスチャ・物体の異常検知
- **MIIC**: カスタムデータセット

詳細はプラットフォーム管理者に確認してください。

### Q4: GPU はどのくらい使えますか？

**A**: ジョブごとに1つのGPUが割り当てられます。実行時間の制限については管理者に確認してください。

### Q5: 投稿したファイルは削除できますか？

**A**: 現在、Web UI からの削除機能はありません。管理者に問い合わせてください。

### Q6: カスタムライブラリを使いたいです

**A**: 現在、標準環境（anomalib、PyTorch、scikit-learnなど）のみサポートしています。追加ライブラリが必要な場合は管理者に相談してください。

### Q7: 結果はいつまで保存されますか？

**A**: MLflow に記録された結果は永続的に保存されます。ただし、ストレージ容量に応じて古い結果が削除される場合があります。

### Q8: 複数のモデルを同時に投稿できますか？

**A**: いいえ、同時に実行できるジョブは1つのみです。
実行中のジョブが完了するまで、新しいジョブを投稿してもキューで待機状態になります。
ジョブが完了したら、次のジョブが自動的に開始されます。

### Q9: エラーコードの意味を教えてください

**A**: 主なエラーコード：

- **401 Unauthorized**: API Token が無効または期限切れ
- **429 Too Many Requests**: レート制限を超過
- **400 Bad Request**: リクエストの形式が不正
- **500 Internal Server Error**: サーバー側のエラー（管理者に報告）

### Q10: 投稿前にローカルでテストできますか？

**A**: はい、推奨します。以下の手順でローカル環境を構築できます：

```bash
# 必要なライブラリをインストール
pip install anomalib omegaconf

# ローカルで実行（引数を指定）
python main.py --config config.yaml --output ./output

# metrics.json が生成されることを確認
cat ./output/metrics.json
```

## サポート

問題が解決しない場合は、以下の情報を添えて管理者に問い合わせてください：

- **Job ID**: ジョブの識別子
- **エラーメッセージ**: ログに表示されたエラー
- **投稿ファイル**: `main.py` と `config.yaml`
- **実行環境**: 使用したブラウザやOSの情報

---

Happy Submitting! 🚀
