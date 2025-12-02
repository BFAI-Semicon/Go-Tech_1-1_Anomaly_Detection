# リーダーズボード最小構成デザインドック

## 目的と範囲

- 本ドキュメントは「外部からの投稿 → サーバーで学習/評価 → MLflowで可視化」を、最小構成で実現する設計のみを記載します。  
- 将来の拡張（EvalAI/高度なRBAC/大規模スケール）は対象外（付録や別ドキュメントで扱う）。

## システム構成（最小）

- API: FastAPI（投稿/ジョブ/進捗/結果のREST）
- キュー: Redis（非同期ジョブ投入）
- ワーカー: GPUコンテナ（anomalibで学習・評価、MLflowへ記録）
- 実験可視化: MLflow Tracking Server（UI/REST）
- ストレージ: 共有ボリューム（ローカルファイル。コード/データ/アーティファクト）
- 提出UI（任意最小）: Streamlit（提出フォーム＋ジョブ一覧/リンク）。無くてもAPIだけで運用可能

備考: MLflowのDBは最小では内蔵SQLiteで可（PoC想定）。運用で並行性が増える場合はRDB（Postgres等）へ移行。

## データフロー（最小）

1. 投稿準備: 認証後、`POST /submissions` で提出メタを登録（アップロード先は共有ボリューム）。  
2. アップロード: クライアントがAPIへ直接アップロード（マルチパート）。  
3. 実行要求: `POST /jobs` で提出IDと設定を指定し、Redisキューへ投入（APIはWorkerへ通知せず、Workerはブロッキング取得で待機）。  
4. 学習/評価: GPUワーカーが提出物を取り出し anomalib で実行、`MLFLOW_TRACKING_URI` を用いて結果を記録。  
5. 可視化: MLflow UIの比較ビューでランキング（リーダーズボード相当）を閲覧。  
6. 参照: `GET /jobs/{id}/status|logs|results` で進捗/ログ/`run_id` 等を取得（`results` は `run_id` と MLflow UI/REST へのリンクを返す。API は MLflow のバックエンドDBを直接参照しない）。

## API（最小エンドポイント）

- `POST /submissions`（提出メタ登録 → アップロード受付）
- `POST /jobs`（提出IDと実行設定を指定してジョブ投入）
- `GET /jobs/{id}/status` / `GET /jobs/{id}/logs` / `GET /jobs/{id}/results`
- `GET /leaderboard`（任意。MLflow UI を使うなら省略可能）

備考: API は MLflow のバックエンドDBには直接依存せず、結果は `run_id` と MLflow UI へのリンクを返す方針とする（依存逆転）。

## 設計方針（Clean-lite 依存逆転）

- 目的: プロトタイプ段階でも、API/Worker をデータベースや特定実装に結合させず、将来の差し替えコストを最小化する。  
- 構成（ドメイン/ポート/アダプタ）
  - ドメイン（ユースケース）: `CreateSubmission`, `EnqueueJob`, `GetJobStatus`, `GetResults`
  - ポート（API/Worker が依存する抽象）:
    - `StoragePort`（提出ファイル保存/参照）
    - `JobQueuePort`（ジョブ投入/取り出し）
    - `JobStatusPort`（状態の保存/参照）
    - `TrackingPort`（メトリクス記録・`run_id` 生成。Worker のみ使用）
  - アダプタ（実装）:
    - ファイルシステム: `/shared/submissions`, `/shared/jobs/*.json` など
    - Redis: キュー/状態管理
    - MLflow Tracking Server: HTTP/REST での計測・記録（バックエンドDBへの直依存なし）
- 境界の責務
  - API: 認証、入力正規化・バリデーション、冪等化、レート制限、ジョブ投入、ステータス集約、`run_id` と MLflow UI へのリンク返却（DB 直読はしない）
  - Worker: 学習/評価の実行、TrackingPort 経由での記録、JobStatusPort 経由での進捗更新

## ワーカー実行（最小仕様）

- 実行環境: Docker（nvidia-container-runtime）でGPU割当。  
- 入力: 共有ボリューム上のコード/データ（提出IDに紐づくパス）を作業ディレクトリへ展開。  
- 実行: anomalibの学習/評価スクリプトを起動。  
- 出力: メトリクス/アーティファクトを MLflow へ記録、補助成果物は共有ボリュームに保存（MLflowのartifact_uriは`file://`を使用）。  
- リソース: タイムアウトとCPU/GPU/メモリ上限（small/medium の2クラス程度）。
- 依存: MLflow Tracking Server の REST/HTTP のみ（バックエンドDBには非依存）。

### キュー待機方式（ブロッキング取得）

- 概要: Worker はキューに仕事が入るまで待機し、入った瞬間に取り出して処理する方式。  
- 実現方法: Redis List の `BRPOP`、または Redis Streams の `XREADGROUP BLOCK` を使用。  
- 待機中の負荷: CPU 使用は極小でポーリング不要（空振りアクセスが発生しない）。  
- 起動の仕組み: 新しいジョブが入ると、Redis が待機中のコマンドに応答し、Worker が即時に“起きる”。  
- API の役割: API はジョブをキューに入れるだけで、Worker への通知は不要。  
- 複数 Worker: 最初に応答した 1 台が 1 件を取得（自然に水平スケール）。  
- タイムアウト: ブロックにタイムアウトを設定し、定期ヘルスチェックやグレースフル停止が可能。  
- 信頼性: at-least-once 前提。冪等性キー（`job_id`）で重複投入を無害化。  
- 耐久性: 本番では AOF 永続化や Redis Streams＋再配布（未ACK）/DLQ の活用を推奨。  

## MLflow ログ指針（最小）

- params: method, dataset, epochs, batch_size など主要ハイパラ  
- metrics:  
  - 画像: `image_auc`, `image_f1`  
  - ピクセル: `pixel_auc`, `pixel_f1`, `pixel_pro`  
  - 付帯: `inference_time_ms`, `vram_mb`
- artifacts: ROC/PR/PRO曲線画像、可視化、ログ、モデル（必要に応じて）

例（最小の記録コード）

```python
import os, mlflow

mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
with mlflow.start_run(run_name=run_name):
    mlflow.log_params({"method": method, "dataset": dataset, "epochs": epochs})
    mlflow.log_metric("image_auc", image_auc)
    mlflow.log_metric("pixel_pro", pixel_pro)
    mlflow.log_artifact("reports/curves.png")
```

## セキュリティと公開（最小）

- 認証: APIトークン（固定発行 or OIDCのトークン検証のどちらか一方）  
- アップロード: APIへ直接アップロード（マルチパート、サイズ上限/CORS設定）  
- 実行隔離: 非特権ユーザー、読み取り専用FS（出力のみ書込）、外向き通信は原則遮断  
- レート制限/クォータ: 1ユーザーあたり提出回数・同時実行数の上限  
- 公開: 最小構成では MLflow は社内（VPN）または認証付きで限定公開

## デプロイ（最小）

- 単機構成: docker-compose（FastAPI, Redis, MLflow, Worker, 任意でStreamlit）  
- 前提: NVIDIAドライバ + nvidia-container-runtime、`.env` に MLflow のURI・共有ディレクトリのパス

## コンテナ構成（最小: docker-compose）

### サービス一覧

- API（FastAPI）
  - 役割: 提出受付（マルチパートアップロード）、認証、入力正規化・バリデーション、冪等化、レート制限、ジョブ投入、ステータス集約、`run_id` と MLflow UI リンクの返却（MLflow DB 直参照なし）
  - ポート: 8000
  - 環境変数（例）:
    - `REDIS_URL=redis://redis:6379/0`
    - `UPLOAD_ROOT=/shared/submissions`
    - 任意: `MLFLOW_TRACKING_URI=http://mlflow:5000`（MLflow UI へのリンク生成に用いる場合のみ）
  - ボリューム: `shared:/shared`
  - 依存: `redis`

- Worker（GPU, anomalib）
  - 役割: キュー（Redis）を消費し、anomalib で学習/評価を実行して MLflow に記録
  - GPU: `--gpus all`（`nvidia-container-runtime`）
  - 環境変数（例）:
    - `MLFLOW_TRACKING_URI=http://mlflow:5000`
    - `REDIS_URL=redis://redis:6379/0`
    - `UPLOAD_ROOT=/shared/submissions`
    - `ARTIFACT_ROOT=/shared/artifacts`
  - ボリューム: `shared:/shared`
  - 依存: `redis`, `mlflow`

- Redis
  - 役割: キュー（Celery/RQ 等）
  - ポート: 6379

- MLflow（Tracking Server）
  - 役割: 実験のパラメータ/メトリクス/アーティファクトの記録・閲覧
  - ポート: 5000
  - 環境変数（例）:
    - `BACKEND_STORE_URI=sqlite:////shared/mlflow.db`
    - `DEFAULT_ARTIFACT_ROOT=file:///shared/artifacts`
  - ボリューム: `shared:/shared`

### ボリューム規約（共有ディレクトリ）

- `/shared/submissions`（投稿コード・データの展開先）
- `/shared/artifacts`（アーティファクト保管先、MLflowの artifact_root）
- `/shared/logs`（任意。学習/評価ログ）
- `/shared/jobs`（任意。ジョブ状態やメタの JSON を冗長保存）
- `/shared/mlflow.db`（SQLite バックエンドストア）

### ポートと起動順

- ポートまとめ: API=8000, MLflow=5000, Redis=6379
- 起動順序（目安）: `redis` → `mlflow` → `api`/`worker`

### 任意の追加（後から拡張）

- Streamlit（提出ポータル/一覧/MLflow へのリンク）
- 逆プロキシ（Nginx 等, 認証/TLS を前段で付与）

## 将来拡張（本最小構成の外）

- ユーザー/RBACの強化、Postgres化、Kubernetes移行、オートスケール  
- 一般公開チャレンジ（EvalAI 前段導入）やランキングの公式公開

---
