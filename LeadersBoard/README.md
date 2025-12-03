# LeadersBoard

ML実験プラットフォーム - 外部からの投稿を受け付け、GPU学習・評価を実行し、MLflowで結果を可視化するリーダーボード機能を提供します。

## 概要

- **提出受付**: 認証済みユーザーからのコード/データのアップロード
- **非同期ジョブ実行**: Redisキュー + GPUワーカーによる学習・評価
- **実験可視化**: MLflow Tracking Serverによるメトリクス・アーティファクトの記録と比較

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

| サービス | ポート | 説明 |
|----------|--------|------|
| API | 8010 | FastAPI REST API |
| MLflow | 5010 | 実験管理UI |
| Redis | 6379 | ジョブキュー |
| Worker | - | GPU学習・評価ワーカー |

## 環境変数

`.env.example`を参照してください。

## ライセンス

TBD
