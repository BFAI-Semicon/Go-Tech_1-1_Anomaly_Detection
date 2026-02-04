# Design Document - leaders-board

## 設計概要

本設計は、外部からの投稿（コード/データ）を受け付け、サーバー側でGPU学習・評価を実行し、MLflowで実験結果を可視化・比較するリーダーボード機能を、Clean-lite設計（依存逆転）により最小構成で実現します。

## アーキテクチャ原則

### Clean-lite設計（依存逆転）

- **目的**: プロトタイプ段階でも、API/Workerをデータベースや特定実装に結合させず、将来の差し替えコストを最小化
- **構成**: ドメイン/ポート/アダプタパターン
  - **ドメイン層**: ビジネスロジック・ユースケース（外部実装に非依存）
  - **ポート層**: 抽象インタフェース（`StoragePort`, `JobQueuePort`, `JobStatusPort`, `TrackingPort`）
  - **アダプタ層**: 具体実装（ファイルシステム、Redis、MLflow Tracking Server）

### 依存方向

```text
ドメイン → ポート（抽象）のみ依存
アダプタ → ポート実装（ドメインには非依存）
API/Worker → ドメイン + アダプタ（DIで注入）
```

## システム構成

### コンポーネント図

```text
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────────────────┐
│           API (FastAPI)                     │
│  - 認証 (APIトークン/OIDC)                  │
│  - バリデーション                           │
│  - レート制限                               │
│  - 冪等化                                   │
└──────┬──────────────────────┬───────────────┘
       │                      │
       │ Redis                │ /shared/
       ▼                      ▼
┌─────────────┐        ┌─────────────┐
│    Redis    │        │   Shared    │
│   (Queue)   │        │   Volume    │
└──────┬──────┘        └─────────────┘
       │ BRPOP                │
       ▼                      │
┌─────────────────────────────┴───────────────┐
│         Worker (GPU Container)              │
│  - anomalib 学習・評価                      │
│  - MLflow 記録 (HTTP/REST)                  │
└──────┬──────────────────────────────────────┘
       │ HTTP/REST
       ▼
┌─────────────────────────────────────────────┐
│      MLflow Tracking Server                 │
│  - パラメータ・メトリクス記録               │
│  - アーティファクト保存                     │
│  - UI (比較ビュー)                          │
└─────────────────────────────────────────────┘
```

### コンポーネント一覧

#### API (FastAPI)

- **役割**: 提出受付、認証、バリデーション、冪等化、レート制限、ジョブ投入、ステータス集約
- **ポート**: 8010
- **依存ポート**:
  - `StoragePort`: 提出ファイル保存
  - `JobQueuePort`: ジョブ投入
  - `JobStatusPort`: 状態参照
- **環境変数**:
  - `REDIS_URL=redis://redis:6379/0`
  - `UPLOAD_ROOT=/shared/submissions`
  - `MLFLOW_TRACKING_URI=http://mlflow:5010` (任意: UIリンク生成用)

#### Worker (GPU Container)

- **役割**: Redisキュー消費、anomalib学習・評価、MLflow記録
- **GPU**: `--gpus all` (nvidia-container-runtime)
- **依存ポート**:
  - `JobQueuePort`: ジョブ取り出し
  - `JobStatusPort`: 進捗更新
  - `StoragePort`: 提出ファイル読み取り
  - `TrackingPort`: MLflow記録
- **環境変数**:
  - `MLFLOW_TRACKING_URI=http://mlflow:5010`
  - `REDIS_URL=redis://redis:6379/0`
  - `UPLOAD_ROOT=/shared/submissions`
  - `ARTIFACT_ROOT=/shared/artifacts`

#### Redis

- **役割**: ジョブキュー、状態管理
- **ポート**: 6379
- **キュー方式**: ブロッキング取得 (`BRPOP` または `XREADGROUP BLOCK`)
- **信頼性**: at-least-once配信、冪等性キー (`job_id`) で重複無害化

#### MLflow Tracking Server

- **役割**: 実験記録・可視化
- **ポート**: 5010
- **バックエンドストア**: SQLite (`/shared/mlflow.db`) ※初期構成、並行性増加時はPostgres移行
- **アーティファクトストア**: ローカルファイル (`file:///shared/artifacts`)

#### Streamlit UI (任意)

- **役割**: 提出フォーム、ジョブ一覧、MLflowリンク表示
- **ポート**: 8501 (例)

## データフロー

### 1. 提出受付フロー

```text
Client → POST /submissions (認証、メタデータ、entrypoint, config_file)
       → マルチパートアップロード (main.py, config.yaml, requirements.txt等)
       → バリデーション (ファイルサイズ、拡張子、パストラバーサル)
       → StoragePort.save() → /shared/submissions/{submission_id}/
       → 応答: submission_id
```

**投稿ファイル構造（規約）**:

```text
/shared/submissions/{submission_id}/
├── main.py          # エントリポイント（デフォルト）
├── config.yaml      # ハイパーパラメータ（デフォルト）
├── requirements.txt # 依存関係（任意）
├── src/            # 追加コード（任意）
│   └── model.py
└── data/           # カスタムデータ（任意）
    └── custom.csv
```

### 2. ジョブ投入フロー

```text
Client → POST /jobs (submission_id, config)
       → 冪等性チェック (job_id)
       → JobQueuePort.enqueue(job_id, submission_id, config)
       → Redis LPUSH
       → 応答: job_id, status=pending
```

### 3. ジョブ実行フロー

```text
Worker → JobQueuePort.dequeue() → Redis BRPOP (ブロッキング待機)
       → ジョブ取得 (job_id, submission_id, entrypoint, config_file)
       → JobStatusPort.update(job_id, status=running)
       → StoragePort.load(submission_id) → /shared/submissions/{submission_id}/
       → パス検証 (entrypoint, config_file)
       → 実行: python {entrypoint} --config {config_file} --output /shared/artifacts/{job_id}
       → (投稿者のコードが MLFLOW_TRACKING_URI 経由で MLflow に記録)
       → JobStatusPort.update(job_id, status=completed, run_id=...)
```

**エントリポイント規約**:

投稿者は以下の規約に従う `main.py` を提供：

```python
# main.py (投稿者が提供)
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    # 1. 画像データを学習用と予測用に分割
    # 2. 学習実行
    # 3. 予測実行
    # 4. 性能指標計測
    
    # 結果をJSONファイルに出力（MLflowに依存しない）
    results = {
        "params": {
            "method": "padim",
            "dataset": "mvtec_ad",
            "epochs": 10
        },
        "metrics": {
            "image_auc": 0.985,
            "pixel_pro": 0.92
        }
    }
    
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    with open(output_path / "metrics.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
```

### 4. 結果取得フロー

```text
Client → GET /jobs/{job_id}/status
       → JobStatusPort.get_status(job_id)
       → 応答: {status, run_id, mlflow_ui_link}

Client → GET /jobs/{job_id}/logs
       → StoragePort.load_logs(job_id)
       → 応答: logs

Client → GET /jobs/{job_id}/results
       → JobStatusPort.get_status(job_id)
       → 応答: {run_id, mlflow_ui_link, mlflow_rest_link}
```

### 5. リーダーボード表示フロー

```text
Client → MLflow UI (http://mlflow:5010)
       → 実験一覧・比較ビュー・メトリクスソート

または

Client → GET /leaderboard (任意)
       → MLflow REST API経由でメトリクス取得
       → ソート・整形
       → 応答: ランキング一覧
```

## ドメイン設計

### ユースケース

#### CreateSubmission

- **入力**: user_id, files, metadata (entrypoint, config_file)
- **処理**:
  1. バリデーション (ファイルサイズ、拡張子、パストラバーサル)
  2. エントリポイント検証 (entrypoint存在確認、`.py` 拡張子チェック)
  3. submission_id 生成
  4. StoragePort.save(submission_id, files)
  5. メタデータ保存 (entrypoint, config_file)
- **出力**: submission_id

#### EnqueueJob

- **入力**: submission_id, config, user_id
- **処理**:
  1. submission存在確認
  2. job_id 生成 (冪等性キー)
  3. レート制限チェック
  4. JobQueuePort.enqueue(job_id, submission_id, config)
  5. JobStatusPort.create(job_id, status=pending)
- **出力**: job_id

#### ExecuteJob (Worker)

<!-- markdownlint-disable MD013 -->
- **入力**: job_id, submission_id, entrypoint, config_file, resource_class
- **処理**:
  1. JobStatusPort.update(job_id, status=running)
  2. submission_dir = StoragePort.load(submission_id)
  3. パス検証 (entrypoint, config_file にパストラバーサルがないか確認)
  4. 実行: `subprocess.run(["python", f"{submission_dir}/{entrypoint}", "--config", f"{submission_dir}/{config_file}", "--output", f"/shared/artifacts/{job_id}"])`
  5. タイムアウト・リソース制限適用
  6. `{output_dir}/metrics.json` を読み込み
  7. TrackingPort.start_run() でMLflow runを開始
  8. TrackingPort.log_params() でパラメータを記録
  9. TrackingPort.log_metrics() でメトリクスを記録
  10. TrackingPort.log_artifacts() でアーティファクトを記録（任意）
  11. run_id = TrackingPort.end_run() で run_id を取得
  12. JobStatusPort.update(job_id, status=completed, run_id=run_id)
- **出力**: run_id
- **注**: 投稿者のコードはMLflowに依存せず、結果をJSONファイルに出力する
<!-- markdownlint-enable MD013 -->

#### GetJobStatus

- **入力**: job_id
- **処理**: JobStatusPort.get_status(job_id)
- **出力**: {status, run_id, created_at, updated_at}

#### GetJobResults

- **入力**: job_id
- **処理**:
  1. JobStatusPort.get_status(job_id)
  2. MLflow UIリンク生成 (run_id)
- **出力**: {run_id, mlflow_ui_link, mlflow_rest_link}

## ポート定義

### StoragePort

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, List

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

### JobQueuePort

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class JobQueuePort(ABC):
    @abstractmethod
    def enqueue(
        self,
        job_id: str,
        submission_id: str,
        entrypoint: str,
        config_file: str,
        config: Dict[str, Any]
    ) -> None:
        """ジョブをキューに投入 (entrypoint, config_file含む)"""
        pass

    @abstractmethod
    def dequeue(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """ジョブをキューから取り出し (ブロッキング)
        返却値: {job_id, submission_id, entrypoint, config_file, config}
        """
        pass
```

### JobStatusPort

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class JobStatusPort(ABC):
    @abstractmethod
    def create(self, job_id: str, submission_id: str, user_id: str) -> None:
        """ジョブ状態を作成"""
        pass

    @abstractmethod
    def update(self, job_id: str, status: JobStatus, **kwargs) -> None:
        """ジョブ状態を更新 (run_id, error_message等)"""
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """ジョブ状態を取得"""
        pass
```

### TrackingPort

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class TrackingPort(ABC):
    @abstractmethod
    def start_run(self, run_name: str) -> str:
        """MLflow runを開始"""
        pass

    @abstractmethod
    def log_params(self, params: Dict[str, Any]) -> None:
        """パラメータを記録"""
        pass

    @abstractmethod
    def log_metrics(self, metrics: Dict[str, float]) -> None:
        """メトリクスを記録"""
        pass

    @abstractmethod
    def log_artifact(self, local_path: str) -> None:
        """アーティファクトを記録"""
        pass

    @abstractmethod
    def end_run(self) -> str:
        """MLflow runを終了し、run_idを返す"""
        pass
```

## アダプタ実装

### FileSystemStorageAdapter

- **実装**: `StoragePort`
- **保存先**: `/shared/submissions/{submission_id}/`
- **メタデータ保存**: `/shared/submissions/{submission_id}/metadata.json` (entrypoint, config_file等)
- **ログ保存**: `/shared/logs/{job_id}.log`
- **バリデーション**:
  - パストラバーサル防止: `..`, `/` を含むパスを拒否
  - エントリポイント存在確認: `{submission_id}/{entrypoint}` が存在するか確認
  - 拡張子チェック: entrypoint は `.py` で終わる必要がある

### RedisJobQueueAdapter

- **実装**: `JobQueuePort`
- **キュー名**: `leaderboard:jobs`
- **方式**: Redis List (`LPUSH` / `BRPOP`) または Redis Streams
- **タイムアウト**: `BRPOP` は30秒タイムアウト（ヘルスチェック用）
- **ペイロード**: JSON形式 `{job_id, submission_id, entrypoint, config_file, config}`

### RedisJobStatusAdapter

- **実装**: `JobStatusPort`
- **保存形式**: Redis Hash (`HSET` / `HGETALL`)
- **キー**: `leaderboard:job:{job_id}`
- **フィールド**: `status`, `submission_id`, `user_id`, `run_id`, `created_at`, `updated_at`, `error_message`

### MLflowTrackingAdapter

- **実装**: `TrackingPort`
- **接続**: `MLFLOW_TRACKING_URI` 経由 (HTTP/REST)
- **依存**: MLflow Python SDK (`mlflow.start_run`, `mlflow.log_params`, etc.)

## API設計

### エンドポイント一覧

#### POST /submissions

- **認証**: APIトークン または OIDC
- **リクエスト**: `multipart/form-data`
  - `files`: アップロードファイル (複数可: `main.py`, `config.yaml`, `requirements.txt`, etc.)
  - `entrypoint`: エントリポイントファイル名 (デフォルト: `main.py`)
  - `config_file`: 設定ファイル名 (デフォルト: `config.yaml`)
  - `metadata`: JSON (method, dataset, etc.)
- **バリデーション**:
  - ファイルサイズ上限: 100MB (設定可能)
  - 拡張子: `.py`, `.yaml`, `.zip`, `.tar.gz`
  - パストラバーサル: `entrypoint`, `config_file` に `..`, `/` が含まれないこと
  - エントリポイント存在: アップロードファイルに `entrypoint` が含まれること
  - エントリポイント拡張子: `.py` で終わること
- **レスポンス**: `201 Created`

```json
{
  "submission_id": "sub_abc123",
  "entrypoint": "main.py",
  "config_file": "config.yaml",
  "created_at": "2025-12-02T06:44:37Z"
}
```

#### POST /jobs

- **認証**: APIトークン または OIDC
- **リクエスト**: `application/json`

```json
{
  "submission_id": "sub_abc123",
  "config": {
    "dataset": "mvtec_ad",
    "method": "padim",
    "epochs": 10,
    "resource_class": "small"
  }
}
```

- **冪等性**: `job_id` はリクエストボディのハッシュで生成
- **レート制限**: 1ユーザーあたり 10提出/時間、同時実行3件
- **レスポンス**: `202 Accepted`

```json
{
  "job_id": "job_xyz789",
  "status": "pending",
  "created_at": "2025-12-02T06:44:37Z"
}
```

#### GET /jobs/{job_id}/status

- **認証**: APIトークン または OIDC
- **レスポンス**: `200 OK`

```json
{
  "job_id": "job_xyz789",
  "status": "completed",
  "run_id": "abc123def456",
  "created_at": "2025-12-02T06:44:37Z",
  "updated_at": "2025-12-02T06:50:12Z"
}
```

#### GET /jobs/{job_id}/logs

- **認証**: APIトークン または OIDC
- **レスポンス**: `200 OK` (text/plain)

```text
[2025-12-02 06:45:00] Starting job job_xyz789
[2025-12-02 06:45:05] Loading submission sub_abc123
[2025-12-02 06:45:10] Running anomalib training...
...
```

#### GET /jobs/{job_id}/results

- **認証**: APIトークン または OIDC
- **レスポンス**: `200 OK`

```json
{
  "job_id": "job_xyz789",
  "run_id": "abc123def456",
  "mlflow_ui_link": "http://mlflow:5010/#/experiments/1/runs/abc123def456",
  "mlflow_rest_link": "http://mlflow:5010/api/2.0/mlflow/runs/get?run_id=abc123def456"
}
```

#### GET /leaderboard (任意)

- **認証**: APIトークン または OIDC
- **クエリパラメータ**:
  - `metric`: ソートメトリクス (例: `image_auc`, `pixel_pro`)
  - `limit`: 取得件数 (デフォルト: 10)
- **レスポンス**: `200 OK`

```json
{
  "metric": "image_auc",
  "entries": [
    {
      "rank": 1,
      "run_id": "abc123def456",
      "user_id": "user1",
      "method": "padim",
      "image_auc": 0.985,
      "created_at": "2025-12-02T06:50:12Z"
    }
  ]
}
```

## セキュリティ設計

### 認証

- **APIトークン**: 固定発行 (初期構成)
  - ヘッダー: `Authorization: Bearer <token>`
  - 検証: 環境変数 `API_TOKENS` (カンマ区切り) と照合
- **OIDC**: 将来拡張
  - トークン検証: `jwks_uri` 経由で公開鍵取得

### 実行隔離

- **非特権ユーザー**: Workerコンテナは `USER 1000:1000` で実行
- **読み取り専用ファイルシステム**: `read_only: true` + 出力ディレクトリのみ書込可能

```yaml
services:
  worker:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - shared:/shared
      - ./submissions:/submissions:ro
```

- **外向き通信遮断**: `network_mode: internal` または iptables設定

### レート制限

- **提出回数**: 1ユーザーあたり 10提出/時間
- **同時実行**: 1ユーザーあたり 3件
- **実装**: Redis カウンター (`INCR` + `EXPIRE`)

### バリデーション

- **ファイルサイズ**: 100MB上限
- **拡張子**: `.py`, `.yaml`, `.zip`, `.tar.gz` のみ
- **パストラバーサル**: `entrypoint`, `config_file` に `..`, `/` が含まれないこと
- **エントリポイント検証**:
  - アップロードファイルに `entrypoint` が含まれること
  - `entrypoint` は `.py` で終わること
- **CORS**: 許可オリジンリスト (環境変数 `ALLOWED_ORIGINS`)

## 性能設計

### 目標

- 提出受付: P95 500ms以内
- ジョブ投入: P95 100ms以内
- 状態取得: P95 200ms以内
- 学習・評価: データセット・手法に依存 (タイムアウト設定で制御)

### キャッシュ戦略

- **ジョブ状態**: Redis Hash (TTL 90日)
- **MLflowメトリクス**: MLflow UI側でキャッシュ (設定外)

### リソース制御

- **Workerクラス**:
  - `small`: 1 GPU, 8GB VRAM, 16GB RAM, タイムアウト 30分
  - `medium`: 1 GPU, 16GB VRAM, 32GB RAM, タイムアウト 60分

## 可観測性

### メトリクス

- **API**: リクエスト数、レイテンシ、エラー率 (Prometheus形式)
- **Worker**: ジョブ実行数、成功率、実行時間、GPU使用率
- **Redis**: キュー長、待機時間

### ログ

- **構造化ログ**: JSON形式 (timestamp, level, message, context)
- **出力先**: stdout (docker-compose logs で収集)

### トレーシング

- **将来拡張**: OpenTelemetry (API → Worker → MLflow の分散トレース)

## デプロイ設計

### docker-compose構成

```yaml
version: '3.8'

services:
  api:
    build: ./api
    ports:
      - "8010:8010"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - UPLOAD_ROOT=/shared/submissions
      - MLFLOW_TRACKING_URI=http://mlflow:5010
    volumes:
      - shared:/shared
    depends_on:
      - redis

  worker:
    build: ./worker
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

  streamlit:
    build: ./streamlit
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://api:8010
      - MLFLOW_TRACKING_URI=http://mlflow:5010
    depends_on:
      - api

volumes:
  shared:
  redis-data:
```

### 環境変数 (.env)

```bash
# API
REDIS_URL=redis://redis:6379/0
UPLOAD_ROOT=/shared/submissions
MLFLOW_TRACKING_URI=http://mlflow:5010
API_TOKENS=token1,token2,token3
ALLOWED_ORIGINS=http://localhost:8501

# Worker
ARTIFACT_ROOT=/shared/artifacts

# MLflow
BACKEND_STORE_URI=sqlite:////shared/mlflow.db
DEFAULT_ARTIFACT_ROOT=file:///shared/artifacts
```

## テスト戦略

### ユニットテスト

- **対象**: ドメインロジック、ポート実装
- **モック**: アダプタをモック化
- **カバレッジ**: 80%以上

### 統合テスト

- **対象**: エンドツーエンドフロー
- **環境**: docker-compose (実Redis・MLflow使用)
- **シナリオ**:
  1. 提出受付 → ジョブ投入 → 実行 → 結果取得
  2. 境界ケース: ファイルサイズ上限、タイムアウト、重複投入
  3. エラーハンドリング: 不正ファイル、OOM、MLflow接続失敗
  4. パストラバーサル攻撃: `entrypoint="../../../etc/passwd"` を拒否
  5. エントリポイント不正: 存在しないファイル、非`.py`拡張子を拒否

### 性能テスト

- **ツール**: Locust
- **シナリオ**: 100ユーザー、10提出/時間
- **検証**: P95レイテンシ、エラー率

## 将来拡張

### Kubernetes移行

- **ストレージ**: 共有ボリューム → S3/PVC
- **キュー**: Redis → RabbitMQ/Kafka
- **Worker**: HPA (Horizontal Pod Autoscaler) でオートスケール

### EvalAI統合

- **チャレンジ管理**: EvalAI前段で提出・評価管理
- **ランキング公開**: EvalAI UIで公式リーダーボード表示

### 高度なRBAC

- **ユーザー管理**: Keycloak/Auth0統合
- **権限**: 提出者/審査員/管理者ロール

### Postgres移行

- **MLflowバックエンド**: SQLite → Postgres (並行性向上)
- **ジョブ状態**: Redis → Postgres (永続性向上)
