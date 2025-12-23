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
  - その他必要なファイル（オプション）

## 投稿の流れ

```text
1. ファイルを準備
   ↓
2. Web UI または API から投稿
   ↓
3. ジョブが自動実行（GPU環境）
   ↓
4. 結果を MLflow UI で確認
   ↓
5. リーダーボードでランキング確認
```

## 投稿方法

### 方法1: Web UI から投稿（推奨）

最も簡単な方法です。

1. ブラウザで `http://localhost:8501` にアクセス
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

#### ステータスの見方

- ⏳ **pending**: ジョブが待機中
- ⏳ **running**: ジョブが実行中
- ✅ **completed**: ジョブが正常に完了
- ❌ **failed**: ジョブが失敗（ログを確認してください）

### 方法2: API から投稿

コマンドラインやスクリプトから投稿する場合。

```bash
# 1. 提出を作成
curl -X POST http://localhost:8010/submissions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@main.py" \
  -F "files=@config.yaml" \
  -F "entrypoint=main.py" \
  -F "config_file=config.yaml" \
  -F 'metadata={"method":"padim","description":"My model"}'

# レスポンス例
# {"submission_id": "abc123"}

# 2. ジョブを投入
curl -X POST http://localhost:8010/jobs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"abc123","config":{"resource_class":"medium"}}'

# レスポンス例
# {"job_id": "xyz789", "status": "pending"}

# 3. ステータスを確認
curl http://localhost:8010/jobs/xyz789/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. ログを確認
curl http://localhost:8010/jobs/xyz789/logs \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 結果の確認

### MLflow UI でメトリクスを確認

1. ブラウザで `http://localhost:5010` にアクセス
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

- **1時間あたりの投稿数**: 最大10回
- **同時実行ジョブ数**: 最大3個

制限を超えると、エラーメッセージが表示されます。

### ファイル要件

#### `main.py` の要件

- **必須関数**: `train()` または `main()` 関数を実装
- **MLflow連携**: `mlflow.log_metric()` でメトリクスを記録
- **エラーハンドリング**: 例外が発生した場合は適切にログ出力

#### `config.yaml` の要件

- **YAML形式**: 有効なYAML構文
- **必須フィールド**: モデル、データ、学習設定を含む
- **サンプル**: 後述の「サンプルコード」を参照

### 評価基準

投稿されたモデルは以下の基準で評価されます：

- **AUROC** (Area Under ROC Curve): 異常検知性能の主要指標
- **F1スコア**: 精度と再現率のバランス
- **実行時間**: 学習・評価にかかった時間
- **その他**: カスタムメトリクス（オプション）

## サンプルコード

### 最小構成の `main.py`

```python
import mlflow
from anomalib.engine import Engine

def main():
    """
    モデルの学習と評価を実行する関数
    """
    # MLflow実験を開始
    mlflow.set_experiment("my-experiment")
    
    with mlflow.start_run():
        # 設定ファイルを読み込み
        engine = Engine.from_config("config.yaml")
        
        # 学習
        engine.train()
        
        # 評価
        results = engine.test()
        
        # メトリクスを記録
        mlflow.log_metric("auroc", results["auroc"])
        mlflow.log_metric("f1_score", results["f1_score"])
        
        print(f"AUROC: {results['auroc']:.4f}")
        print(f"F1 Score: {results['f1_score']:.4f}")

if __name__ == "__main__":
    main()
```

### 最小構成の `config.yaml`

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
    root: pcb1/Data/Images
    normal_dir: Normal
    abnormal_dir: Anomaly
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

### より詳細な `main.py` の例

```python
import mlflow
import logging
from pathlib import Path
from anomalib.engine import Engine

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """
    カスタムメトリクスとアーティファクトを含む投稿例
    """
    # 実験名とタグを設定
    mlflow.set_experiment("my-advanced-experiment")
    
    with mlflow.start_run():
        # タグを追加
        mlflow.set_tag("model", "padim")
        mlflow.set_tag("backbone", "resnet18")
        
        # パラメータを記録
        mlflow.log_param("max_epochs", 10)
        mlflow.log_param("batch_size", 32)
        
        try:
            # エンジンを初期化
            logger.info("Initializing engine...")
            engine = Engine.from_config("config.yaml")
            
            # 学習
            logger.info("Starting training...")
            engine.train()
            
            # 評価
            logger.info("Starting evaluation...")
            results = engine.test()
            
            # メトリクスを記録
            mlflow.log_metric("auroc", results["auroc"])
            mlflow.log_metric("f1_score", results["f1_score"])
            
            # カスタムメトリクス（オプション）
            if "precision" in results:
                mlflow.log_metric("precision", results["precision"])
            if "recall" in results:
                mlflow.log_metric("recall", results["recall"])
            
            # アーティファクトを記録（オプション）
            # 例: 可視化画像、混同行列など
            output_dir = Path("outputs")
            if output_dir.exists():
                mlflow.log_artifacts(str(output_dir))
            
            logger.info(f"Training completed successfully!")
            logger.info(f"AUROC: {results['auroc']:.4f}")
            logger.info(f"F1 Score: {results['f1_score']:.4f}")
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            mlflow.log_param("status", "failed")
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

**A**: はい、レート制限の範囲内であれば可能です。ただし、同時実行ジョブ数は最大3個までです。

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
pip install anomalib mlflow

# ローカルで実行
python main.py
```

## サポート

問題が解決しない場合は、以下の情報を添えて管理者に問い合わせてください：

- **Job ID**: ジョブの識別子
- **エラーメッセージ**: ログに表示されたエラー
- **投稿ファイル**: `main.py` と `config.yaml`
- **実行環境**: 使用したブラウザやOSの情報

---

Happy Submitting! 🚀
