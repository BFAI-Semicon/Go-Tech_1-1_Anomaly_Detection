# LeadersBoard

ML実験プラットフォーム - 外部からの投稿を受け付け、GPU学習・評価を実行し、MLflowで結果を可視化するリーダーボード機能を提供します。

## 概要

LeadersBoard は、Clean-lite 設計（依存逆転）を採用した ML 実験プラットフォームです。anomalib を用いた異常検知モデルの評価を想定した最小構成から開始し、将来的にはスケールアウトやクラウド移行に対応できる設計となっています。

### 主要機能

- **提出受付**: 認証済みユーザーからのコード/データのアップロード
- **非同期ジョブ実行**: Redisキュー + GPUワーカーによる学習・評価
- **実験可視化**: MLflow Tracking Serverによるメトリクス・アーティファクトの記録と比較
- **Web UI**: Streamlit UIによる提出フォーム、ジョブ監視、ログ表示（自動更新対応）
- **リーダーボード**: MLflow UIの比較ビューを活用したランキング表示

### アーキテクチャ特徴

- **Clean-lite設計**: ドメイン/ポート/アダプタによる依存逆転
- **ポータビリティ**: MLflowバックエンドDB非依存（HTTP/REST のみ使用）
- **テスト駆動**: カバレッジ75%以上、62件のユニットテスト + 10件の統合テスト
- **将来拡張**: ファイルシステム→S3、Redis→RabbitMQ、SQLite→Postgresへの移行が容易

## クイックスタート

### 開発環境（devcontainer）

1. VS Code/Cursorでプロジェクトを開く
2. 「Reopen in Container」を選択
3. コンテナが起動したら、以下のコマンドでAPIを起動:

```bash
cd /workspaces/2025/LeadersBoard
python -m src.api.main
```

### 本番環境

```bash
cd LeadersBoard
docker-compose -f docker-compose.yml up --build
```

## ディレクトリ構造

```text
LeadersBoard/
├── src/
│   ├── domain/      # ビジネスロジック・ユースケース
│   ├── ports/       # 抽象インタフェース
│   ├── adapters/    # 具体実装（Redis, MLflow等）
│   ├── api/         # FastAPI エンドポイント
│   └── worker/      # ジョブ実行ワーカー
├── tests/
│   ├── unit/        # ユニットテスト
│   └── integration/ # 統合テスト
├── docker/
│   ├── api.Dockerfile      # API用（マルチステージ: dev/prod）
│   └── worker.Dockerfile   # Worker用（GPU対応）
├── docker-compose.yml          # 本番用構成
├── docker-compose.override.yml # 開発用オーバーライド
├── requirements.txt            # 本番依存関係
├── requirements-dev.txt        # 開発依存関係
└── pyproject.toml              # プロジェクト設定
```

## 開発コマンド

```bash
# テスト実行
pytest tests/ --cov

# Lint
ruff check .
black --check .

# フォーマット
black .
isort .

# 型チェック
mypy src/
```

## サービス

| サービス  | ポート | 説明                               |
| --------- | ------ | ---------------------------------- |
| API       | 8010   | FastAPI REST API                   |
| Streamlit | 8501   | Web UI（提出フォーム、ジョブ監視） |
| MLflow    | 5010   | 実験管理UI                         |
| Redis     | 6379   | ジョブキュー                       |
| Worker    | -      | GPU学習・評価ワーカー              |

## 使用方法

### Web UI から提出（推奨）

1. ブラウザで `http://localhost:8501` にアクセス
2. API Token を入力（開発環境: `devtoken`）
3. ファイルをアップロード（`main.py`, `config.yaml` など）
4. Submit ボタンをクリック
5. ジョブ一覧で進捗を確認（5秒ごとに自動更新）

### API 経由で提出

```bash
# 1. 提出を作成
curl -X POST http://localhost:8010/submissions \
  -H "Authorization: Bearer devtoken" \
  -F "files=@main.py" \
  -F "files=@config.yaml" \
  -F "entrypoint=main.py" \
  -F "config_file=config.yaml" \
  -F 'metadata={"method":"padim"}'

# レスポンス例: {"submission_id": "abc123"}

# 2. ジョブを投入
curl -X POST http://localhost:8010/jobs \
  -H "Authorization: Bearer devtoken" \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"abc123","config":{"resource_class":"medium"}}'

# レスポンス例: {"job_id": "xyz789", "status": "pending"}

# 3. ステータスを確認
curl http://localhost:8010/jobs/xyz789/status \
  -H "Authorization: Bearer devtoken"

# 4. ログを取得
curl http://localhost:8010/jobs/xyz789/logs \
  -H "Authorization: Bearer devtoken"

# 5. 結果を取得
curl http://localhost:8010/jobs/xyz789/results \
  -H "Authorization: Bearer devtoken"
```

## API 仕様

### エンドポイント一覧

| メソッド | エンドポイント           | 説明                                  |
| -------- | ------------------------ | ------------------------------------- |
| POST     | `/submissions`           | 提出を作成                            |
| POST     | `/jobs`                  | ジョブを投入                          |
| GET      | `/jobs/{job_id}/status`  | ジョブ状態を取得                      |
| GET      | `/jobs/{job_id}/logs`    | ジョブログを取得                      |
| GET      | `/jobs/{job_id}/results` | ジョブ結果を取得（MLflow リンク含む） |

詳細は `http://localhost:8010/docs` の OpenAPI 仕様を参照してください。

## 環境変数

`.env.example`を参照してください。

主要な環境変数：

- `REDIS_URL`: Redis接続URL（デフォルト: `redis://redis:6379/0`）
- `MLFLOW_TRACKING_URI`: MLflow Tracking Server URL（デフォルト: `http://mlflow:5010`）
- `API_TOKENS`: 認証トークン（カンマ区切り、デフォルト: `devtoken`）
- `UPLOAD_ROOT`: 提出ファイル保存先（デフォルト: `/shared/submissions`）
- `LOG_ROOT`: ログ保存先（デフォルト: `/shared/logs`）

## トラブルシューティング

### GPU が認識されない

```bash
# nvidia-container-runtime が正しくインストールされているか確認
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Worker が起動しない

```bash
# Worker ログを確認
docker-compose logs -f worker
```

### テストが失敗する

```bash
# 統合テストは Redis と MLflow が必要
docker-compose up -d redis mlflow
pytest tests/integration/
```

## ライセンス

TBD
