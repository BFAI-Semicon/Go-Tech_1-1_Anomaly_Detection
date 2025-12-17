# Technology Stack

## Architecture

- **Clean-lite設計（依存逆転）**: API/WorkerはMLflowバックエンドDBに直接依存せず、HTTP/RESTのみ使用
- **ポート/アダプタパターン**: `StoragePort`, `JobQueuePort`, `JobStatusPort`, `TrackingPort`
- **非同期ジョブ実行**: Redisキュー（ブロッキング取得: `BRPOP` または `XREADGROUP BLOCK`）+ GPUワーカー
- **コンテナベース**: docker-compose単機構成（FastAPI、Redis、MLflow、Worker、任意でStreamlit）

## API Authentication

- API は `Authorization: Bearer <token>` を必須とし、`get_current_user` によって `API_TOKENS` 環境変数のカンマ区切りリストへ照合。リストが空でもヘッダー自体は必須なので、トークンベースの保護を環境変数で集中管理できる設計。
- この認証依存性は FastAPI の依存性注入で `jobs` / `submissions` ルーター間で再利用され、コード上の各エンドポイントが同じトークンロジックを参照。

## Core Technologies

- **Language**: Python 3.13
- **API Framework**: FastAPI（提出受付、ジョブ投入、状態取得）
- **Queue**: Redis（非同期ジョブ投入、at-least-once配信）
- **Worker**: GPUコンテナ（nvidia-container-runtime、anomalib学習・評価）
- **Experiment Tracking**: MLflow Tracking Server（パラメータ・メトリクス・アーティファクト記録）
- **UI**: MLflow UI（実験可視化）、将来的にStreamlit UI追加予定

### Container Runtime

- **Base Image (GPU)**: `nvcr.io/nvidia/pytorch:25.11-py3`（PyTorch 2.10 開発版、CUDA 対応）
- **起動方式（API）**: `uvicorn`（`src.api.main:app`）
- **起動方式（Worker）**: `python -m src.worker.main`

## Key Libraries

- **anomalib**: 異常検知モデルの学習・評価フレームワーク
- **MLflow**: 実験管理・可視化（Tracking Server、UI、REST API）
- **Redis**: キュー・状態管理（`redis-py`）
- **FastAPI**: REST API（認証、バリデーション、レート制限）
- **Pydantic**: 入力正規化・バリデーション

## Submission Handling

- `CreateSubmission` は `MAX_FILE_SIZE = 100MB` を超えないファイルのみ受け入れる。
- 拡張子は `.py`, `.yaml`, `.zip`, `.tar.gz` のホワイトリストに限定している。
- エントリポイント・設定ファイル名にはパストラバーサルを防ぐ検証を行っている。
- 提出時に受け取った `metadata` フィールドは JSON オブジェクトとしてパースされる。
- `user_id`, `entrypoint`, `config_file` を含むメタ情報とマージして `metadata.json` に書き込む。
- `FileSystemStorageAdapter` は `UPLOAD_ROOT`/`LOG_ROOT` を自動作成し、ファイル一覧（`files`）とメタデータをまとめて保持する。
- 同アダプタは `load_logs(job_id)` で `<LOG_ROOT>/<job_id>.log` を返却し、API の `/jobs/{job_id}/logs` エンドポイントからワーカー出力を提供できるようインタフェースを揃えている。

## Rate Limiting

- **Purpose**: API がジョブ投入前にユーザーごとの提出処理数と実行中ジョブ数を確認し、公平性を維持する。
- **Domain Policy**: `EnqueueJob` は `MAX_SUBMISSIONS_PER_HOUR = 10` と  
  `MAX_CONCURRENT_RUNNING = 3` を順番に検証する。  
  `JobStatusPort` のあと `RateLimitPort` を呼び出し、違反時は `ValueError` で拒否する。
- **Implementation**: `RedisRateLimitAdapter` は `leaderboard:rate:` プレフィックスの Redis カウンターを使う。  
  `INCR` + `EXPIRE`（TTL 3600 秒）で提出数を管理し、`increment_submission`/`get_submission_count` を提供する。  
  ドメインは注入されたポート経由で `enqueue` 前のゲートを構築する。

## Development Standards

### Type Safety

- Python 3.13 型ヒント必須（`mypy` strict mode推奨）
- Pydanticモデルで入力・出力の型安全性を担保

### Code Quality

- **Linter**: `ruff` または `flake8` + `black`
- **Formatter**: `black`
- **Import Order**: `isort`

### Process Lifecycle（Worker）

- **待機**: キュー実装が入るまでの暫定措置として、低負荷の待機ループでプロセスを維持
- **終了**: `SIGTERM` / `SIGINT` を捕捉し、グレースフルシャットダウン（`threading.Event` 等で中断）
- **将来置換**: 待機ループは、`BRPOP` または `XREADGROUP BLOCK` を用いるブロッキング待機（`JobWorker.run()`）に置換予定

### Testing

- **Framework**: `pytest`
- **Coverage**: 80%以上推奨（ドメインロジック・ポート実装は必須）
  - **現在の達成状況**: 46.3%（継続的改善中）
  - **テスト数**: 77件のテスト関数
- **Integration Test**: docker-compose環境でエンドツーエンドテスト
- **Test Organization**:
  - `/tests/unit/` - モックアダプタを使用した高速テスト
  - `/tests/integration/` - 実Redis・MLflowを使用したE2Eテスト

## Development Environment

### Required Tools

- Docker + docker-compose
- NVIDIAドライバ + nvidia-container-runtime（GPU必須）
- Python 3.13
- `.env` ファイル（MLflow URI、共有ディレクトリパス）

### devcontainer統合

- **構成**: `docker-compose.yml`（本番） + `docker-compose.override.yml`（開発オーバーライド）
- **マルチステージビルド**: `api.Dockerfile`に`dev`/`prod`ステージを定義
- **devcontainer.json**: 両ファイルを参照し、`api`サービスに接続
- **API開発**: devcontainer（apiコンテナ）内で直接実行（Cursorデバッガー対応）
- **Worker開発**: GPUコンテナ内で実行（nvidia-container-runtime必須）
  - デバッグ: ログベース + ユニットテスト（モックアダプタ）
  - Workerのビジネスロジックはドメイン層に分離し、devcontainer内でテスト可能
- **依存サービス**: Redis, MLflow, Workerはdocker-composeサービスとして起動

### docker-compose構成

```yaml
# docker-compose.yml（本番用）
services:
  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
      target: prod  # 本番ステージ
    # ...

# docker-compose.override.yml（開発用オーバーライド）
services:
  api:
    build:
      target: dev  # 開発ステージに切り替え
    volumes:
      - ..:/workspaces/2025:cached  # ソースマウント
```

### 開発フロー

```bash
# devcontainer起動時に自動でapi(dev), Redis, MLflow, Workerが起動
# APIはdevcontainer内で直接実行（デバッガー使用可能）
python -m src.api.main

# Workerログ確認
docker-compose logs -f worker

# ユニットテスト（devcontainer内）
pytest tests/unit/ --cov

# 統合テスト（全サービス使用）
pytest tests/integration/

# 本番ビルド確認（override無視）
docker-compose -f docker-compose.yml up --build
```

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

### ジョブ状態トラッキングと実行

- `RedisJobStatusAdapter` は `leaderboard:job:<job_id>` ハッシュを使ってステータスとメタ情報を保持し、TTL を 90 日間維持する。
- `count_running` は `SCAN` で running 状態を持つエントリを集計し、`EnqueueJob` の同時実行制限へ渡す。
- `JobWorker` は entrypoint と設定ファイルを `python` に渡し、artifact ルートへ成果物を出力する。
- 実行は `subprocess.run(..., timeout=...)` で行う。
- `resource_class`（small/medium）が指定されていれば `RESOURCE_TIMEOUTS` からタイムアウトを選ぶ。
- **投稿者のコードは `metrics.json` を出力し、MLflowに依存しない**。
- Worker が `metrics.json` を読み取り、`TrackingPort` 経由で MLflow に記録する。
- `TrackingPort.end_run()` から `run_id` を取得して `JobStatus.COMPLETED` を更新する。
- 例外・タイムアウト・OOM・metrics.json 不在/不正時には `FAILED` として `error` メッセージを保存する。

## Maintenance

- updated_at: 2025-12-17
- reason: プロジェクト状態を最新化（Streamlit UI削除、テストカバレッジ実測値反映、実装進捗更新）
