# Implementation Tasks - leaders-board

## タスク概要

本ドキュメントは、ML実験プラットフォーム「LeadersBoard」の実装タスクを定義します。Clean-lite設計（ドメイン/ポート/アダプタ）に基づき、段階的に実装を進めます。

## 実装フェーズ

### フェーズ1: 基盤構築

docker-compose環境、ポート定義、基本アダプタの実装

### フェーズ2: API実装

提出受付、ジョブ投入、状態取得のエンドポイント実装

### フェーズ3: Worker実装

Redisキュー消費、ジョブ実行、MLflow記録

### フェーズ4: 統合・テスト

エンドツーエンドテスト、性能テスト、セキュリティテスト

## タスク一覧

### T1: プロジェクト初期化

**優先度**: P0（最優先）  
**依存**: なし

#### 実装内容

##### 1. プロジェクトディレクトリ構造作成

- [x] ディレクトリ構造を作成
- [x] 各ディレクトリに `__init__.py` を配置

```text
leaders-board/
├── src/
│   ├── domain/
│   ├── ports/
│   ├── adapters/
│   ├── api/
│   └── worker/
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
│   ├── api.Dockerfile (マルチステージ: dev/prod)
│   ├── worker.Dockerfile
│   ├── streamlit.Dockerfile (任意)
│   └── mlflow.Dockerfile (任意: カスタマイズ時のみ)
├── docker-compose.yml (本番用)
├── docker-compose.override.yml (開発用オーバーライド)
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── README.md
```

**注**:

- MLflowは公式イメージ（`ghcr.io/mlflow/mlflow:latest`）を使用するため、基本的にはDockerfileは不要です。認証追加やプラグイン導入などのカスタマイズが必要な場合のみ、`docker/mlflow.Dockerfile` を作成します。
- `api.Dockerfile`はマルチステージビルドで`dev`（開発）と`prod`（本番）の2ステージを持ちます。
- `docker-compose.override.yml`は開発時に自動適用され、apiのtargetを`dev`に切り替えます。

##### 2. 依存関係ファイル作成

- [x] `requirements.txt` 作成（FastAPI, Redis, MLflow, Pydantic等）
- [x] `requirements-dev.txt` 作成（pytest, ruff, black, isort, mypy, debugpy等）
- [x] `requirements-worker.txt` 作成（torch, anomalib, redis, mlflow, opencv等）
- [x] `pyproject.toml` 作成（ruff, black, isort, mypy設定）

##### 3. 環境変数テンプレート作成

- [x] `.env.example` 作成（REDIS_URL, MLFLOW_TRACKING_URI, API_TOKENS等）

##### 4. docker-compose.yml（本番用）作成

- [x] Redis サービス定義
- [x] MLflow サービス定義
- [x] API サービス定義（target: prod）
- [x] Worker サービス定義（GPU対応）
- [x] 共有ボリューム定義

```yaml
services:
  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
      target: prod
    ports:
      - "8010:8010"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - MLFLOW_TRACKING_URI=http://mlflow:5010
    volumes:
      - shared:/shared
    depends_on:
      - redis
      - mlflow

  worker:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    environment:
      - MLFLOW_TRACKING_URI=http://mlflow:5010
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - shared:/shared
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - redis
      - mlflow

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports:
      - "5010:5010"
    environment:
      - BACKEND_STORE_URI=sqlite:////shared/mlflow.db
      - DEFAULT_ARTIFACT_ROOT=file:///shared/artifacts
    volumes:
      - shared:/shared
    command: mlflow server --host 0.0.0.0 --port 5010

volumes:
  shared:
  redis-data:
```

##### 5. docker-compose.override.yml（開発用）作成

- [x] API サービスのtargetをdevに変更
- [x] ソースコードのボリュームマウント設定

```yaml
# 開発時に自動適用（devcontainer用）
services:
  api:
    build:
      target: dev  # 開発ステージに切り替え
    volumes:
      - ..:/workspaces/2025:cached
      - shared:/shared
    # 開発時はコンテナ内でpython -m src.api.mainを直接実行
    command: sleep infinity
```

##### 6. Dockerfile作成

- [x] `docker/api.Dockerfile` 作成（マルチステージ: dev/prod）
- [x] `docker/worker.Dockerfile` 作成

```dockerfile
# docker/api.Dockerfile (マルチステージ)

# ベースステージ
FROM python:3.13-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 開発ステージ
FROM base AS dev
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
# ソースはボリュームマウントで提供

# 本番ステージ
FROM base AS prod
COPY src/ ./src/
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

```dockerfile
# docker/worker.Dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "-m", "src.worker.main"]
```

##### 7. devcontainer.json更新

- [x] `.devcontainer/devcontainer.json` を更新（dockerComposeFile指定）

```json
{
  "name": "LeadersBoard Dev",
  "dockerComposeFile": [
    "../LeadersBoard/docker-compose.yml",
    "../LeadersBoard/docker-compose.override.yml"
  ],
  "service": "api",
  "workspaceFolder": "/workspaces/2025",
  "customizations": {
    "vscode": {
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python"
      },
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.black-formatter",
        "ms-python.mypy-type-checker"
      ]
    }
  },
  "forwardPorts": [8010, 5010, 6379],
  "remoteUser": "root"
}
```

#### 受け入れ基準

- ディレクトリ構造が作成され、空の `__init__.py` が配置されている
- `requirements.txt`、`requirements-dev.txt` に必要な依存関係が記載されている
- `.env.example` に環境変数テンプレートが記載されている
- `docker-compose up redis mlflow` でRedisとMLflowが起動する
- `docker-compose up worker` でWorkerが起動する（GPU環境）
- devcontainerが起動し、Cursorから接続できる
- devcontainer内で `python -m src.api.main` が実行可能（空のmain.pyでOK）

---

### T2: ポート定義実装

**優先度**: P0  
**依存**: T1

#### 実装内容

##### 1. `src/ports/storage_port.py`: StoragePort抽象クラス

- [x] StoragePort抽象クラスを実装
- [x] 全メソッドに型ヒントとdocstringを記載

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, List, Dict, Any

class StoragePort(ABC):
    @abstractmethod
    def save(self, submission_id: str, files: List[BinaryIO], metadata: Dict[str, Any]) -> None:
        """提出ファイルとメタデータを保存"""
        pass

    @abstractmethod
    def load(self, submission_id: str) -> str:
        """提出ファイルのパスを返す"""
        pass

    @abstractmethod
    def load_metadata(self, submission_id: str) -> Dict[str, Any]:
        """提出メタデータ (entrypoint, config_file等) を取得"""
        pass

    @abstractmethod
    def exists(self, submission_id: str) -> bool:
        """提出が存在するか確認"""
        pass

    @abstractmethod
    def validate_entrypoint(self, submission_id: str, entrypoint: str) -> bool:
        """エントリポイントの存在と安全性を検証"""
        pass

    @abstractmethod
    def load_logs(self, job_id: str) -> str:
        """ジョブログを取得"""
        pass
```

##### 2. その他のポート

- [x] `src/ports/job_queue_port.py`: JobQueuePort抽象クラスを実装
- [x] `src/ports/job_status_port.py`: JobStatusPort抽象クラスを実装
- [x] `src/ports/tracking_port.py`: TrackingPort抽象クラスを実装
- [x] ユニットテスト作成（`tests/unit/test_ports.py`）

#### 受け入れ基準

- 4つのポート抽象クラスが定義されている
- 型ヒントが完全に記載されている
- docstringが記載されている
- ユニットテストが通過する

---

### T3: FileSystemStorageAdapter実装

**優先度**: P0  
**依存**: T2

#### 実装内容

##### 1. `src/adapters/filesystem_storage_adapter.py`

- [ ] `save()` 実装: `/shared/submissions/{submission_id}/` にファイル保存、`metadata.json` 保存
- [ ] `load()` 実装: 提出ディレクトリパス返却
- [ ] `load_metadata()` 実装: `metadata.json` 読み込み
- [ ] `exists()` 実装: ディレクトリ存在確認
- [ ] `validate_entrypoint()` 実装: パストラバーサル防止、拡張子チェック、存在確認
- [ ] `load_logs()` 実装: `/shared/logs/{job_id}.log` 読み込み

##### 2. バリデーション実装

- [ ] パストラバーサル防止: `..`, `/` を含むパスを拒否
- [ ] 拡張子チェック: entrypoint は `.py` で終わる必要がある
- [ ] ユニットテスト作成（`tests/unit/test_filesystem_storage_adapter.py`、モックファイルシステム使用）

#### 受け入れ基準

- StoragePortを実装している
- ユニットテストが通過する（モックファイルシステム使用）
- パストラバーサル攻撃を防げる

---

### T4: RedisJobQueueAdapter実装

**優先度**: P0  
**依存**: T2

#### 実装内容

##### 1. `src/adapters/redis_job_queue_adapter.py`

- [ ] `enqueue()` 実装: Redis LPUSH でジョブ投入、ペイロード: `{job_id, submission_id, entrypoint, config_file, config}`
- [ ] `dequeue()` 実装: Redis BRPOP でジョブ取り出し（タイムアウト30秒）

##### 2. Redis接続管理

- [ ] `redis-py` 使用して接続実装
- [ ] 接続プール設定
- [ ] ユニットテスト作成（`tests/unit/test_redis_job_queue_adapter.py`、fakeredis使用）

#### 受け入れ基準

- JobQueuePortを実装している
- ユニットテストが通過する（fakeredis使用）
- ブロッキング取得が動作する

---

### T5: RedisJobStatusAdapter実装

**優先度**: P0  
**依存**: T2

#### 実装内容

##### 1. `src/adapters/redis_job_status_adapter.py`

- [ ] `create()` 実装: Redis HSET でジョブ状態作成
- [ ] `update()` 実装: Redis HSET でジョブ状態更新
- [ ] `get_status()` 実装: Redis HGETALL でジョブ状態取得

##### 2. ステータス管理

- [ ] キー設計: `leaderboard:job:{job_id}`
- [ ] フィールド定義: `status`, `submission_id`, `user_id`, `run_id`, `created_at`, `updated_at`, `error_message`
- [ ] TTL設定: 90日
- [ ] ユニットテスト作成（`tests/unit/test_redis_job_status_adapter.py`、fakeredis使用）

#### 受け入れ基準

- JobStatusPortを実装している
- ユニットテストが通過する（fakeredis使用）
- TTL設定が動作する

---

### T6: MLflowTrackingAdapter実装

**優先度**: P1  
**依存**: T2

#### 実装内容

##### 1. `src/adapters/mlflow_tracking_adapter.py`

- [ ] `start_run()` 実装: `mlflow.start_run()` ラップ
- [ ] `log_params()` 実装: `mlflow.log_params()` ラップ
- [ ] `log_metrics()` 実装: `mlflow.log_metrics()` ラップ
- [ ] `log_artifact()` 実装: `mlflow.log_artifact()` ラップ
- [ ] `end_run()` 実装: `mlflow.end_run()` ラップ、run_id返却

##### 2. MLflow接続設定

- [ ] `MLFLOW_TRACKING_URI` 環境変数から取得する実装
- [ ] ユニットテスト作成（`tests/unit/test_mlflow_tracking_adapter.py`、モックMLflow使用）

#### 受け入れ基準

- TrackingPortを実装している
- ユニットテストが通過する（モックMLflow使用）

---

### T7: ドメインロジック実装（CreateSubmission）

**優先度**: P0  
**依存**: T3

#### 実装内容

##### 1. `src/domain/create_submission.py`

- [ ] CreateSubmissionクラス実装
- [ ] バリデーションロジック実装
- [ ] エントリポイント検証実装
- [ ] storage.save呼び出し実装

```python
class CreateSubmission:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    def execute(self, user_id: str, files: List[BinaryIO], entrypoint: str = "main.py", config_file: str = "config.yaml", metadata: Dict[str, Any] = None) -> str:
        # 1. バリデーション (ファイルサイズ、拡張子)
        # 2. submission_id 生成
        # 3. エントリポイント検証
        # 4. storage.save(submission_id, files, metadata)
        return submission_id
```

##### 2. バリデーション

- [ ] ファイルサイズ上限チェック: 100MB
- [ ] 拡張子チェック: `.py`, `.yaml`, `.zip`, `.tar.gz`
- [ ] パストラバーサルチェック: `entrypoint`, `config_file` に `..`, `/` が含まれないこと
- [ ] ユニットテスト作成（`tests/unit/test_create_submission.py`、モックStoragePort使用）

#### 受け入れ基準

- ユニットテストが通過する（モックStoragePort使用）
- バリデーションエラーが適切に発生する

---

### T8: ドメインロジック実装（EnqueueJob）

**優先度**: P0  
**依存**: T4, T5

#### 実装内容

##### 1. `src/domain/enqueue_job.py`

- [ ] EnqueueJobクラス実装
- [ ] submission存在確認実装
- [ ] メタデータ取得実装
- [ ] job_id生成（冪等性キー）実装
- [ ] レート制限チェック実装
- [ ] queue.enqueue呼び出し実装
- [ ] status.create呼び出し実装

```python
class EnqueueJob:
    def __init__(self, storage: StoragePort, queue: JobQueuePort, status: JobStatusPort):
        self.storage = storage
        self.queue = queue
        self.status = status

    def execute(self, submission_id: str, user_id: str, config: Dict[str, Any]) -> str:
        # 1. submission存在確認
        # 2. メタデータ取得 (entrypoint, config_file)
        # 3. job_id 生成 (冪等性キー)
        # 4. レート制限チェック (Redis カウンター)
        # 5. queue.enqueue(job_id, submission_id, entrypoint, config_file, config)
        # 6. status.create(job_id, status=pending)
        return job_id
```

##### 2. レート制限

- [ ] 提出回数制限実装: 1ユーザーあたり 10提出/時間
- [ ] 同時実行制限実装: 3件
- [ ] Redis カウンター実装 (`INCR` + `EXPIRE`)
- [ ] ユニットテスト作成（`tests/unit/test_enqueue_job.py`、モックポート使用）

#### 受け入れ基準

- ユニットテストが通過する
- レート制限が動作する
- 冪等性が担保される

---

### T9: ドメインロジック実装（GetJobStatus, GetJobResults）

**優先度**: P1  
**依存**: T5

#### 実装内容

##### 1. `src/domain/get_job_status.py`

- [ ] GetJobStatusクラス実装
- [ ] status.get_status呼び出し実装

```python
class GetJobStatus:
    def __init__(self, status: JobStatusPort):
        self.status = status

    def execute(self, job_id: str) -> Dict[str, Any]:
        return self.status.get_status(job_id)
```

##### 2. `src/domain/get_job_results.py`

- [ ] GetJobResultsクラス実装
- [ ] MLflow UIリンク生成実装
- [ ] MLflow RESTリンク生成実装
- [ ] ユニットテスト作成（`tests/unit/test_get_job_status.py`, `tests/unit/test_get_job_results.py`）

```python
class GetJobResults:
    def __init__(self, status: JobStatusPort, mlflow_uri: str):
        self.status = status
        self.mlflow_uri = mlflow_uri

    def execute(self, job_id: str) -> Dict[str, Any]:
        status = self.status.get_status(job_id)
        run_id = status.get("run_id")
        return {
            "job_id": job_id,
            "run_id": run_id,
            "mlflow_ui_link": f"{self.mlflow_uri}/#/experiments/1/runs/{run_id}",
            "mlflow_rest_link": f"{self.mlflow_uri}/api/2.0/mlflow/runs/get?run_id={run_id}"
        }
```

#### 受け入れ基準

- ユニットテストが通過する

---

### T10: FastAPI エンドポイント実装（POST /submissions）

**優先度**: P0  
**依存**: T7

#### 実装内容

##### 1. `src/api/submissions.py`

- [ ] POST /submissions エンドポイント実装
- [ ] マルチパートファイルアップロード処理実装
- [ ] CreateSubmission.execute呼び出し実装
- [ ] レスポンス返却実装

```python
@router.post("/submissions", status_code=201)
async def create_submission(
    files: List[UploadFile] = File(...),
    entrypoint: str = Form("main.py"),
    config_file: str = Form("config.yaml"),
    metadata: str = Form("{}"),
    user_id: str = Depends(get_current_user)
):
    # 1. 認証 (APIトークン検証)
    # 2. バリデーション
    # 3. CreateSubmission.execute()
    # 4. レスポンス返却
```

##### 2. 認証ミドルウェア

- [ ] `get_current_user()` 実装: `Authorization: Bearer <token>` 検証
- [ ] 環境変数 `API_TOKENS` と照合実装

##### 3. バリデーション

- [ ] ファイルサイズ上限チェック: 100MB
- [ ] 拡張子チェック実装
- [ ] パストラバーサル防止実装
- [ ] ユニットテスト作成（`tests/unit/test_api_submissions.py`）

#### 受け入れ基準

- エンドポイントが動作する
- 認証が動作する
- バリデーションエラーが適切に返却される
- ユニットテストが通過する

---

### T11: FastAPI エンドポイント実装（POST /jobs）

**優先度**: P0  
**依存**: T8

#### 実装内容

##### 1. `src/api/jobs.py`

- [ ] POST /jobs エンドポイント実装
- [ ] EnqueueJob.execute呼び出し実装
- [ ] レスポンス返却実装

```python
@router.post("/jobs", status_code=202)
async def create_job(
    request: CreateJobRequest,
    user_id: str = Depends(get_current_user)
):
    # 1. 認証
    # 2. EnqueueJob.execute()
    # 3. レスポンス返却
```

##### 2. リクエストモデル

- [ ] CreateJobRequestモデル定義
- [ ] ユニットテスト作成（`tests/unit/test_api_jobs.py`）

```python
class CreateJobRequest(BaseModel):
    submission_id: str
    config: Dict[str, Any]
```

#### 受け入れ基準

- エンドポイントが動作する
- ジョブがRedisキューに投入される
- ユニットテストが通過する

---

### T12: FastAPI エンドポイント実装（GET /jobs/{id}/status|logs|results）

**優先度**: P1  
**依存**: T9

#### 実装内容

##### 1. `src/api/jobs.py`

- [ ] GET /jobs/{job_id}/status エンドポイント実装
- [ ] GET /jobs/{job_id}/logs エンドポイント実装
- [ ] GET /jobs/{job_id}/results エンドポイント実装
- [ ] ユニットテスト作成（`tests/unit/test_api_jobs_get.py`）

```python
@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    # GetJobStatus.execute()

@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, user_id: str = Depends(get_current_user)):
    # StoragePort.load_logs()

@router.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str, user_id: str = Depends(get_current_user)):
    # GetJobResults.execute()
```

#### 受け入れ基準

- 3つのエンドポイントが動作する
- 認証が動作する
- ユニットテストが通過する

---

### T13: Worker実装（ジョブ実行）

**優先度**: P0  
**依存**: T4, T5, T6

#### 実装内容

##### 1. `src/worker/job_worker.py`

- [ ] JobWorkerクラス実装
- [ ] run()メソッド実装（無限ループ、キュー待機）
- [ ] execute_job()メソッド実装
- [ ] パス検証実装
- [ ] subprocess.run実装
- [ ] run_id取得実装
- [ ] 状態更新実装

```python
class JobWorker:
    def __init__(self, queue: JobQueuePort, status: JobStatusPort, storage: StoragePort):
        self.queue = queue
        self.status = status
        self.storage = storage

    def run(self):
        while True:
            job = self.queue.dequeue(timeout=30)
            if job:
                self.execute_job(job)

    def execute_job(self, job: Dict[str, Any]):
        job_id = job["job_id"]
        submission_id = job["submission_id"]
        entrypoint = job["entrypoint"]
        config_file = job["config_file"]

        # 1. status.update(job_id, status=running)
        # 2. submission_dir = storage.load(submission_id)
        # 3. パス検証
        # 4. subprocess.run(["python", f"{submission_dir}/{entrypoint}", "--config", f"{submission_dir}/{config_file}", "--output", f"/shared/artifacts/{job_id}"])
        # 5. タイムアウト・リソース制限適用
        # 6. run_id 取得（標準出力またはMLflow API）
        # 7. status.update(job_id, status=completed, run_id=run_id)
```

##### 2. タイムアウト設定

- [ ] `small`クラス: 30分タイムアウト実装
- [ ] `medium`クラス: 60分タイムアウト実装

##### 3. エラーハンドリング

- [ ] OOM検知・エラー処理実装
- [ ] タイムアウト検知・エラー処理実装
- [ ] status.update(job_id, status=failed, error_message=...) 実装
- [ ] ユニットテスト作成（`tests/unit/test_job_worker.py`、モックポート使用）

#### 受け入れ基準

- Workerがジョブを取り出して実行できる
- タイムアウトが動作する
- エラーハンドリングが動作する
- ユニットテストが通過する

---

### T14: docker-compose構成完成

**優先度**: P0  
**依存**: T10, T11, T12, T13

**注**: T1で基本的なdocker-compose.yml（Redis, MLflow）とDockerfile雛形を作成済みです。このタスクではAPI/Workerサービスを有効化し、本番相当の設定を追加します。

#### 実装内容

##### 1. `docker-compose.yml` 完成（API/Workerサービス有効化）

- [ ] APIサービスのコメントを外して有効化
- [ ] Workerサービスのコメントを外して有効化
- [ ] GPU設定追加
- [ ] read_only設定追加（Worker）
- [ ] 環境変数を`.env`から読み込むよう設定

```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    ports:
      - "8010:8010"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - UPLOAD_ROOT=/shared/submissions
      - MLFLOW_TRACKING_URI=http://mlflow:5010
      - API_TOKENS=${API_TOKENS}
    volumes:
      - shared:/shared
    depends_on:
      - redis

  worker:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    environment:
      - MLFLOW_TRACKING_URI=http://mlflow:5010
      - REDIS_URL=redis://redis:6379/0
      - UPLOAD_ROOT=/shared/submissions
      - ARTIFACT_ROOT=/shared/artifacts
    volumes:
      - shared:/shared
    depends_on:
      - redis
      - mlflow
    read_only: true
    tmpfs:
      - /tmp

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports:
      - "5010:5010"
    environment:
      - BACKEND_STORE_URI=sqlite:////shared/mlflow.db
      - DEFAULT_ARTIFACT_ROOT=file:///shared/artifacts
    volumes:
      - shared:/shared
    command: mlflow server --host 0.0.0.0 --port 5010

volumes:
  shared:
  redis-data:
```

##### 2. Dockerfile完成

- [ ] `docker/api.Dockerfile` 完成: 依存関係インストール、ソースコピー、起動コマンド
- [ ] `docker/worker.Dockerfile` 完成: GPU対応、anomalib、起動コマンド
- [ ] `docker/mlflow.Dockerfile` 作成（任意）: カスタマイズが必要な場合のみ（認証、プラグイン等）

**注**: MLflowは基本的に公式イメージ（`ghcr.io/mlflow/mlflow:latest`）を使用します。

##### 3. 動作確認

- [ ] `docker-compose up` で全サービスが起動することを確認
- [ ] API ヘルスチェック（<http://localhost:8010/docs>）
- [ ] MLflow UI（<http://localhost:5010>）
- [ ] Redisへの接続確認

#### 受け入れ基準

- `docker-compose up` で全サービス（API, Worker, Redis, MLflow）が起動する
- サービス間の通信が正常に動作する
- GPU設定が正しく動作する（Worker）
- 共有ボリュームが正しくマウントされる

---

### T15: 統合テスト実装

**優先度**: P1  
**依存**: T14

#### 実装内容

##### 1. `tests/integration/test_e2e.py`

- [ ] エンドツーエンドテスト実装: 提出受付 → ジョブ投入 → 実行 → 結果取得
- [ ] 境界ケーステスト実装: ファイルサイズ上限、タイムアウト、重複投入
- [ ] エラーハンドリングテスト実装: 不正ファイル、OOM、MLflow接続失敗
- [ ] セキュリティテスト実装: パストラバーサル攻撃（`entrypoint="../../../etc/passwd"`）を拒否
- [ ] エントリポイント不正テスト実装: 存在しないファイル、非`.py`拡張子を拒否

##### 2. テストフィクスチャ

- [ ] サンプル提出ファイル作成（`main.py`, `config.yaml`）
- [ ] docker-compose環境でのテスト実行環境構築

#### 受け入れ基準

- 全統合テストが通過する
- カバレッジ80%以上

---

### T16: Streamlit UI実装（任意）

**優先度**: P2（低優先）  
**依存**: T14

#### 実装内容

##### 1. `src/streamlit/app.py`

- [ ] 提出フォーム実装: ファイルアップロード、entrypoint/config_file指定
- [ ] ジョブ一覧実装: 状態表示、ログ表示
- [ ] MLflowリンク実装: run_id からMLflow UIへのリンク

##### 2. docker-compose追加

- [ ] streamlitサービスをdocker-composeに追加

```yaml
streamlit:
  build:
    context: .
    dockerfile: docker/streamlit.Dockerfile
  ports:
    - "8501:8501"
  environment:
    - API_URL=http://api:8010
    - MLFLOW_URL=http://mlflow:5010
  depends_on:
    - api
```

#### 受け入れ基準

- Streamlit UIが起動する
- 提出フォームが動作する
- ジョブ一覧が表示される

---

### T17: 性能テスト実装

**優先度**: P2  
**依存**: T15

#### 実装内容

##### 1. `tests/performance/locustfile.py`

```python
from locust import HttpUser, task, between

class LeaderboardUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def submit_and_check(self):
        # POST /submissions
        # POST /jobs
        # GET /jobs/{id}/status (ポーリング)
```

##### 2. シナリオ

- [ ] Locustシナリオ実装: 100ユーザー、10提出/時間
- [ ] P95レイテンシ測定実装

#### 受け入れ基準

- 提出受付: P95 500ms以内
- ジョブ投入: P95 100ms以内
- 状態取得: P95 200ms以内

---

### T18: ドキュメント作成

**優先度**: P2  
**依存**: T14

#### 実装内容

##### 1. `README.md`

- [ ] プロジェクト概要記載
- [ ] セットアップ手順記載
- [ ] 使用方法記載
- [ ] API仕様記載

##### 2. `docs/api.md`: OpenAPI仕様（FastAPIから自動生成）

- [ ] OpenAPI仕様を自動生成して文書化

##### 3. `docs/deployment.md`: デプロイ手順

- [ ] デプロイ手順文書作成

#### 受け入れ基準

- README.mdが完成している
- セットアップ手順が明確

---

## タスク依存グラフ

```text
T1 (初期化)
 ├─ T2 (ポート定義)
 │   ├─ T3 (FileSystemStorageAdapter)
 │   │   └─ T7 (CreateSubmission)
 │   │       └─ T10 (POST /submissions)
 │   ├─ T4 (RedisJobQueueAdapter)
 │   │   └─ T8 (EnqueueJob)
 │   │       └─ T11 (POST /jobs)
 │   ├─ T5 (RedisJobStatusAdapter)
 │   │   ├─ T8 (EnqueueJob)
 │   │   └─ T9 (GetJobStatus, GetJobResults)
 │   │       └─ T12 (GET /jobs/{id}/*)
 │   └─ T6 (MLflowTrackingAdapter)
 │       └─ T13 (Worker)
 └─ T14 (docker-compose)
     ├─ T15 (統合テスト)
     │   └─ T17 (性能テスト)
     ├─ T16 (Streamlit UI)
     └─ T18 (ドキュメント)
```

## リスクと軽減策

### リスク1: GPU環境のセットアップ

- **影響**: Worker実装・テストが遅延
- **軽減策**: 事前にGPU環境（nvidia-container-runtime）を準備、CPU fallback実装

### リスク2: MLflow統合の複雑性

- **影響**: Worker実装が遅延
- **軽減策**: MLflow Tracking Serverを先行起動、サンプル実験で動作確認

### リスク3: セキュリティ脆弱性

- **影響**: パストラバーサル攻撃、任意コード実行
- **軽減策**: 統合テストでセキュリティシナリオを優先実装、コードレビュー

## 次のステップ

1. タスク承認後、`/kiro/spec-impl leaders-board` で実装フェーズに進む
2. スプリント1から順次実装
3. 各タスク完了後、プルリクエスト作成・レビュー
