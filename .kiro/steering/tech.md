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
- **UI**:
  - **MLflow UI**: 実験可視化（パラメータ・メトリクス・アーティファクト比較）
  - **Streamlit UI**: 提出フォーム、ジョブ一覧、ログ表示（ポート8501）

### Container Runtime

- **Base Image (GPU)**: `nvcr.io/nvidia/pytorch:25.11-py3`（PyTorch 2.10 開発版、CUDA 対応）
- **起動方式（API）**: `uvicorn`（`src.api.main:app`）
- **起動方式（Worker）**: `python -m src.worker.main`
- **起動方式（Streamlit）**: `streamlit run src/streamlit/app.py --server.port 8501`

## Key Libraries

- **anomalib**: 異常検知モデルの学習・評価フレームワーク
- **MLflow**: 実験管理・可視化（Tracking Server、UI、REST API）
- **Redis**: キュー・状態管理（`redis-py`）
- **FastAPI**: REST API（認証、バリデーション、レート制限）
- **Pydantic**: 入力正規化・バリデーション
- **Streamlit**: Web UI（提出フォーム、ジョブ監視、ログ表示）

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
  `MAX_CONCURRENT_RUNNING = 1` を順番に検証する。  
  `JobStatusPort` のあと `RateLimitPort` を呼び出し、違反時は `ValueError` で拒否する。
- **Implementation**: `RedisRateLimitAdapter` は `leaderboard:rate:` プレフィックスの Redis カウンターを使う。  
  `INCR` + `EXPIRE`（TTL 3600 秒）で提出数を管理し、`increment_submission`/`get_submission_count` を提供する。  
  ドメインは注入されたポート経由で `enqueue` 前のゲートを構築する。

## Development Standards

### Type Safety

- Python 3.13 型ヒント必須（`mypy` strict mode推奨）
- Pydanticモデルで入力・出力の型安全性を担保

### Code Quality

- **Linter**: `ruff`
- **Formatter**: `ruff format`
- **Import Order**: `ruff`（`I`ルール）

### Process Lifecycle（Worker）

- **待機**: キュー実装が入るまでの暫定措置として、低負荷の待機ループでプロセスを維持
- **終了**: `SIGTERM` / `SIGINT` を捕捉し、グレースフルシャットダウン（`threading.Event` 等で中断）
- **将来置換**: 待機ループは、`BRPOP` または `XREADGROUP BLOCK` を用いるブロッキング待機（`JobWorker.run()`）に置換予定

### Testing

- **Framework**: `pytest`
- **Coverage**: 80%以上推奨（ドメインロジック・ポート実装は必須）
  - **現在の達成状況**: 90.8%（目標達成）
  - **テスト数**: 65件（ユニット55件 + 統合10件）
- **Integration Test**: docker-compose環境でエンドツーエンドテスト
- **Test Organization**:
  - `/tests/unit/` - モックアダプタを使用した高速テスト（ドメイン・アダプタ・API・Worker・Streamlit UI）
  - `/tests/integration/` - 実Redis・MLflowを使用したE2Eテスト（10件）
- **Test Coverage**:
  - エンドツーエンドフロー（提出→ジョブ→実行→結果取得）
  - metrics.json読み取りとMLflow記録
  - セキュリティ（パストラバーサル、不正エントリポイント）
  - エラーハンドリング（OOM、タイムアウト、metrics.json不在/不正）
  - 境界ケース（ファイルサイズ上限、重複投入）
  - Streamlit UI（提出フォーム、ジョブ一覧、ログ取得、MLflowリンク生成）

## CI/CD Pipeline

### GitHub Actions

**CI (`.github/workflows/ci.yml`)**:

- **Trigger**: push/PR to `main`
- **Runner**: ubuntu-22.04
- **Steps**: Python 3.13 setup → `ruff check` → `pytest tests/unit`
- **Purpose**: 品質ゲート（静的解析 + ユニットテスト）

**CD (`.github/workflows/deploy.yml`)**:

- **Trigger**: push to `main`（`LeadersBoard/**` 変更時）、または手動実行
- **Runner**: self-hosted (Linux, X64, prod)
- **Steps**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && up -d`
- **Purpose**: 本番環境への自動デプロイ（プリビルドイメージ使用）

### Container Registry

- **Registry**: ghcr.io/bfai-semicon/go-tech-1-1-anomaly/
- **Images**: `api:main`, `worker:main`, `streamlit:main`
- **Usage**: `docker-compose.prod.yml` でイメージ参照

## Development Environment

### Required Tools

- Docker + docker-compose
- NVIDIAドライバ + nvidia-container-runtime（GPU必須）
- Python 3.13
- `.env` ファイル（MLflow URI、共有ディレクトリパス）

### devcontainer統合

- **構成**: `LeadersBoard/docker-compose.yml`（本番） + `.devcontainer/docker-compose.override.yml`（開発オーバーライド）
- **マルチステージビルド**: `api.Dockerfile`に`dev`/`prod`ステージを定義
- **devcontainer.json**: 両ファイルを参照し、`api`サービスに接続
- **API開発**: devcontainer（apiコンテナ）内で直接実行（Cursorデバッガー対応）
- **Worker開発**: GPUコンテナ内で実行（nvidia-container-runtime必須）
  - デバッグ: ログベース + ユニットテスト（モックアダプタ）
  - Workerのビジネスロジックはドメイン層に分離し、devcontainer内でテスト可能
- **依存サービス**: Redis, MLflow, Worker, Streamlitはdocker-composeサービスとして起動

### docker-compose構成

```yaml
# LeadersBoard/docker-compose.yml（本番用）
services:
  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
      target: prod  # 本番ステージ
    # ...

# .devcontainer/docker-compose.override.yml（開発用オーバーライド）
services:
  api:
    build:
      target: dev  # 開発ステージに切り替え
    volumes:
      - ..:/app:cached  # ソースマウント
    command: sleep infinity  # 手動起動用
```

### 開発フロー

```bash
# devcontainer起動時に自動でapi(dev), Redis, MLflow, Worker, Streamlitが起動
# APIはdevcontainer内で直接実行（デバッガー使用可能）
cd /app/LeadersBoard
python -m src.api.main

# Workerログ確認
docker-compose logs -f worker

# ユニットテスト（devcontainer内）
pytest tests/unit/ --cov

# 統合テスト（全サービス使用）
pytest tests/integration/

# 本番ビルド確認（override無視）
cd /app/LeadersBoard
docker-compose -f docker-compose.yml up --build
```

### Common Commands

```bash
# Dev: docker-compose up -d
# Build: docker-compose build
# Test: pytest tests/ --cov
# Lint: ruff check . && ruff format --check .
# Format: ruff format .
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
- **リアルタイムログストリーミング**: `subprocess.Popen()` でサブプロセスを起動し、stdout/stderrをログファイルに直接ストリーミング。`PYTHONUNBUFFERED=1` でPythonのバッファリングを無効化し、ログのリアルタイム出力を実現。
- `resource_class`（small/medium）が指定されていれば `RESOURCE_TIMEOUTS` からタイムアウトを選ぶ。
- **投稿者のコードは `metrics.json` を出力し、MLflowに依存しない**。
- Worker が `metrics.json` を読み取り、`TrackingPort` 経由で MLflow に記録する。
- **パフォーマンスメトリクス**: `metrics.json` の `performance` フィールド（`training_time_seconds`, `peak_gpu_memory_mb`, `inference_time_ms` 等）を `system/` プレフィックス付きで MLflow に追加記録。
- `TrackingPort.end_run()` から `run_id` を取得して `JobStatus.COMPLETED` を更新する。
- 例外・タイムアウト・OOM・metrics.json 不在/不正時には `FAILED` として `error` メッセージを保存する。

## Streamlit UI Implementation

### UI Design

- **Thin Client**: REST API呼び出しでバックエンドと通信（ドメインロジック非依存）
- **Session State**: ジョブ一覧をStreamlitセッションステートで管理
- **Error Handling**: API呼び出し失敗時のユーザーフレンドリーなエラー表示

### Key Features

1. **提出フォーム**: ファイルアップロード、エントリポイント/設定ファイル指定、メタデータJSON入力
2. **ジョブ一覧**: Job ID、Submission ID、ステータス表示（色分け対応）
3. **自動更新**: `@st.fragment(run_every="5s")` による5秒ごとの自動更新（実行中ジョブがある場合のみAPIリクエスト）
4. **MLflow連携**: `run_id`からMLflow UI runリンクを自動生成・表示
5. **リアルタイムログ表示**: 実行中ジョブのログを展開状態で表示、完了ジョブは折りたたみ表示
6. **手動更新**: 🔄ボタンで任意タイミングのログ再取得
7. **パフォーマンス最適化**: 実行中ジョブは最新100行のみ取得（tail処理）

### Integration Pattern

```python
# APIクライアント関数（requests使用）
submit_submission(api_url, token, files, ...) -> dict
create_job(api_url, token, submission_id, config) -> dict
fetch_job_status(api_url, token, job_id) -> dict | None
fetch_job_logs(api_url, token, job_id) -> str

# MLflowリンク生成
build_mlflow_run_link(mlflow_url, run_id) -> str

# ステータス管理
has_running_jobs(jobs) -> bool  # pending/running検出
get_status_color(status) -> str  # ステータス絵文字（✅❌⏳❓）

# Fragment自動更新（main関数内で動的適用）
render_jobs_with_auto_refresh = st.fragment(run_every="5s")(_render_jobs)
```

### Environment Variables

- `API_URL`: FastAPI エンドポイント（デフォルト: `http://api:8010`）
- `MLFLOW_URL`: MLflow UI URL（デフォルト: `http://mlflow:5010`）

### Streamlit Testing

- ユニットテスト: `tests/unit/test_streamlit_app.py`（モックリクエスト使用）
- Streamlit未インストール環境でもテスト可能（オプショナルインポート）

## Documentation Standards

### README.md Structure

- **Overview**: 5分で理解できるプロジェクト説明とアーキテクチャ特徴
- **Quick Start**: 開発環境・本番環境の最速起動手順
- **Usage**: Web UI + API経由の具体的な使用例
- **Troubleshooting**: よくある問題と解決方法

### API Documentation (docs/api.md)

- **Complete Reference**: 全エンドポイントの詳細仕様（リクエスト/レスポンス例含む）
- **Code Contract**: 投稿者のコード規約（metrics.json フォーマット）
- **OpenAPI Integration**: FastAPI自動生成仕様へのリンク（/docs, /redoc）

### Deployment Documentation (docs/deployment.md)

- **Multi-Architecture**: シングルノード（開発）+ マルチノード（本番）構成
- **Operations**: バックアップ、モニタリング、トラブルシューティング
- **Security**: 本番環境チェックリスト

## Maintenance

- updated_at: 2026-02-06
- reason: streamlit-realtime-worker-logs機能（リアルタイムログストリーミング、tail処理、UI改善）を反映
