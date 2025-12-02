# Technology Stack

## Architecture

- **Clean-lite設計（依存逆転）**: API/WorkerはMLflowバックエンドDBに直接依存せず、HTTP/RESTのみ使用
- **ポート/アダプタパターン**: `StoragePort`, `JobQueuePort`, `JobStatusPort`, `TrackingPort`
- **非同期ジョブ実行**: Redisキュー（ブロッキング取得: `BRPOP` または `XREADGROUP BLOCK`）+ GPUワーカー
- **コンテナベース**: docker-compose単機構成（FastAPI、Redis、MLflow、Worker、任意でStreamlit）

## Core Technologies

- **Language**: Python 3.13
- **API Framework**: FastAPI（提出受付、ジョブ投入、状態取得）
- **Queue**: Redis（非同期ジョブ投入、at-least-once配信）
- **Worker**: GPUコンテナ（nvidia-container-runtime、anomalib学習・評価）
- **Experiment Tracking**: MLflow Tracking Server（パラメータ・メトリクス・アーティファクト記録）
- **UI (Optional)**: Streamlit（提出フォーム、ジョブ一覧、MLflowリンク）

## Key Libraries

- **anomalib**: 異常検知モデルの学習・評価フレームワーク
- **MLflow**: 実験管理・可視化（Tracking Server、UI、REST API）
- **Redis**: キュー・状態管理（`redis-py`）
- **FastAPI**: REST API（認証、バリデーション、レート制限）
- **Pydantic**: 入力正規化・バリデーション

## Development Standards

### Type Safety

- Python 3.13 型ヒント必須（`mypy` strict mode推奨）
- Pydanticモデルで入力・出力の型安全性を担保

### Code Quality

- **Linter**: `ruff` または `flake8` + `black`
- **Formatter**: `black`
- **Import Order**: `isort`

### Testing

- **Framework**: `pytest`
- **Coverage**: 80%以上推奨（ドメインロジック・ポート実装は必須）
- **Integration Test**: docker-compose環境でエンドツーエンドテスト

## Development Environment

### Required Tools

- Docker + docker-compose
- NVIDIAドライバ + nvidia-container-runtime（GPU必須）
- Python 3.13
- `.env` ファイル（MLflow URI、共有ディレクトリパス）

### Common Commands

```bash
# Dev: docker-compose up -d
# Build: docker-compose build
# Test: pytest tests/ --cov
# Lint: ruff check . && black --check .
# Format: black . && isort .
```

## Key Technical Decisions

### 依存逆転（Clean-lite設計）

- **目的**: プロトタイプ段階でも、API/Workerをデータベースや特定実装に結合させず、将来の差し替えコストを最小化
- **実装**: ポート（抽象）とアダプタ（実装）を分離
  - ポート: `StoragePort`, `JobQueuePort`, `JobStatusPort`, `TrackingPort`
  - アダプタ: ファイルシステム、Redis、MLflow Tracking Server（HTTP/REST）

### MLflowバックエンドDB非依存

- APIはMLflowバックエンドDBを直接参照せず、`run_id` とMLflow UI/RESTへのリンクを返却
- 将来のMLflow移行（SQLite→Postgres、オンプレ→クラウド）に柔軟対応

### at-least-once配信 + 冪等性

- Redisキューはat-least-once前提
- `job_id` による冪等性キーで重複投入を無害化
- 本番ではRedis AOF永続化、Streams＋再配布（未ACK）/DLQ推奨

### 共有ボリューム（初期）→ S3/PVC（将来）

- 初期: ローカル共有ボリューム（`/shared/submissions`, `/shared/artifacts`）
- 将来: S3互換ストレージ、Kubernetes PVC
