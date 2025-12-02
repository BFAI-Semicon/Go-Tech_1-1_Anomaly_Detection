# Requirements - leaders-board

## プロジェクト概要

外部からの投稿（コード/データ）を受け付け、サーバー側でGPU学習・評価を実行し、MLflowで実験結果を可視化・比較するリーダーボード機能を提供する。anomalibを用いた異常検知モデルの評価を想定した最小構成。

## 目的・ゴール

- 外部ユーザーが提出したモデル/手法を公平に評価し、ランキング形式で可視化する。
- MLflowの比較ビューを活用し、実験結果の透明性と再現性を担保する。
- プロトタイプ段階でも将来の拡張（EvalAI統合、大規模スケール）に備えた設計とする。

## スコープ

- 提出受付API（認証、マルチパートアップロード、メタデータ登録）
- 非同期ジョブ実行（Redisキュー、GPUワーカー、anomalib学習・評価）
- MLflow Tracking Serverへの実験記録（パラメータ、メトリクス、アーティファクト）
- ジョブ進捗・ログ・結果の取得API（`run_id` とMLflow UIリンクの返却）
- リーダーボード表示（MLflow UI比較ビューを活用、または任意の専用エンドポイント）
- 提出UI（任意：Streamlitで提出フォーム・ジョブ一覧・MLflowリンク）

## 非スコープ

- EvalAI等の高度なチャレンジ管理プラットフォーム（将来拡張）
- 高度なRBAC/ユーザー管理（最小構成ではAPIトークンまたはOIDC検証のみ）
- 大規模スケール（Kubernetes、オートスケール）は将来対応
- 不正検知の高度な分析（将来拡張）

## ユーザーストーリー

- 研究者として、自分の手法をアップロードし、標準データセットで評価結果を確認したい。
- 研究者として、他の提出と比較してランキング上の位置を知りたい。
- 管理者として、ジョブの実行状況（進捗、ログ、エラー）を監視したい。
- 管理者として、MLflow UIで全実験のメトリクス・アーティファクトを一覧・比較したい。

## 機能要件

### 提出管理

- `POST /submissions`: 提出メタデータ登録、マルチパートアップロード受付（共有ボリュームへ保存）
- 認証: APIトークン（固定発行）またはOIDCトークン検証
- バリデーション: ファイルサイズ上限、拡張子チェック、CORS設定
- レート制限: 1ユーザーあたり提出回数・同時実行数の上限
- 投稿ファイル構造（規約）:
  - `main.py`: エントリポイント（デフォルト、カスタマイズ可能）
  - `config.yaml`: ハイパーパラメータ設定（デフォルト、カスタマイズ可能）
  - `requirements.txt`: 依存関係（任意）
  - `src/`: 追加Pythonコード（任意）
  - `data/`: カスタムデータ（任意）
- エントリポイント指定: 投稿時に `entrypoint` と `config_file` をメタデータで指定可能（省略時はデフォルト）
- パス検証: パストラバーサル防止（`..`, `/` 禁止）、拡張子チェック（`.py` のみ）

### ジョブ実行

- `POST /jobs`: 提出IDと実行設定を指定し、Redisキューへ投入
- 冪等化: `job_id` による重複投入の無害化
- ワーカー: Redisキューをブロッキング取得（`BRPOP` または `XREADGROUP BLOCK`）し、GPUコンテナで学習・評価を実行
- 実行方式: `python {entrypoint} --config {config_file} --output {output_dir}` 形式で起動
- MLflow記録: `MLFLOW_TRACKING_URI` 環境変数経由でパラメータ・メトリクス・アーティファクトを記録
- リソース制御: タイムアウト、CPU/GPU/メモリ上限（small/mediumクラス）
- エントリポイント規約: 投稿者は `--config` と `--output` 引数を受け取る `main.py` を提供

### 結果取得

- `GET /jobs/{id}/status`: ジョブの状態（pending/running/completed/failed）
- `GET /jobs/{id}/logs`: 実行ログの取得
- `GET /jobs/{id}/results`: `run_id` とMLflow UI/RESTへのリンクを返却（APIはMLflowバックエンドDBを直接参照しない）

### リーダーボード表示

- `GET /leaderboard`（任意）: MLflow UIの比較ビューを使う場合は省略可能
- MLflow UI: 実験一覧・比較ビュー・メトリクスソート機能を活用

### 提出UI（任意）

- Streamlit: 提出フォーム、ジョブ一覧、MLflowリンク表示

## 非機能要件

### 可用性

- API: 99.9%の月間可用性目標（最小構成では単機、将来は冗長化）
- MLflow: 社内（VPN）または認証付きで限定公開

### 性能

- 提出受付: P95で500ms以内
- ジョブ投入: P95で100ms以内
- 状態取得: P95で200ms以内
- 学習・評価: データセット・手法に依存（タイムアウト設定で制御）

### スケーラビリティ

- 初期: docker-compose単機構成（FastAPI、Redis、MLflow、Worker）
- 将来: 複数Workerの水平スケール、Kubernetes移行

### 一貫性

- at-least-once配信（冪等性キーで重複投入を無害化）
- 本番ではRedis AOF永続化、Streams＋再配布（未ACK）/DLQ推奨

### セキュリティ

- 認証: APIトークン（固定発行）またはOIDC検証
- 実行隔離: 非特権ユーザー、読み取り専用ファイルシステム（出力のみ書込）、外向き通信は原則遮断
- アップロード: サイズ上限、拡張子チェック、CORS設定

### 依存逆転（Clean-lite設計）

- API/WorkerはMLflowバックエンドDBに直接依存せず、HTTP/RESTのみ使用
- ポート/アダプタパターン: `StoragePort`, `JobQueuePort`, `JobStatusPort`, `TrackingPort`
- 将来の差し替えコスト最小化（ファイルシステム→S3、Redis→RabbitMQ、SQLite→Postgres等）

## データ要件

### MLflowログ指針

- params: `method`, `dataset`, `epochs`, `batch_size` など主要ハイパーパラメータ
- metrics:
  - 画像: `image_auc`, `image_f1`
  - ピクセル: `pixel_auc`, `pixel_f1`, `pixel_pro`
  - 付帯: `inference_time_ms`, `vram_mb`
- artifacts: ROC/PR/PRO曲線画像、可視化、ログ、モデル（必要に応じて）

### ストレージ

- 共有ボリューム: `/shared/submissions`（投稿）、`/shared/artifacts`（MLflow artifact_root）、`/shared/logs`（任意）、`/shared/jobs`（任意：ジョブメタJSON）、`/shared/mlflow.db`（SQLiteバックエンドストア）
- 保持: 最低90日（将来はアーカイブ戦略を検討）

## 制約

- GPU環境: NVIDIAドライバ + nvidia-container-runtime必須
- 最小構成: docker-compose単機（FastAPI、Redis、MLflow、Worker、任意でStreamlit）
- MLflowバックエンド: 初期はSQLite、並行性増加時はPostgres等へ移行
- 評価フレームワーク: anomalibを前提（将来は他フレームワークも検討）

## 受け入れ基準

- 提出受付からジョブ実行、MLflow記録までのエンドツーエンドが正常動作する
- 代表データセット（例: MVTec AD）で学習・評価が完了し、メトリクスがMLflow UIで確認できる
- ジョブ状態・ログ・結果取得APIが仕様通りに動作する
- 境界ケース（ファイルサイズ上限、タイムアウト、重複投入）で適切にエラーハンドリングされる
- SLA/性能目標（P95）を満たす

## 成功指標

- 提出数・実行成功率の向上
- MLflow UI閲覧率、セッション滞在時間の改善
- API P95/エラー率が目標内に収まる
- ユーザーフィードバック（使いやすさ、透明性）の肯定率

## リスクと軽減策

- GPU不足・高負荷時のキュー滞留 → 複数Worker水平スケール、優先度制御
- ジョブ実行失敗（OOM、タイムアウト） → リソースクラス設定、エラーログ詳細化、DLQ
- MLflow DBロック（SQLite並行性制限） → 早期にPostgres移行
- 不正投稿（悪意あるコード） → 実行隔離、外向き通信遮断、サンドボックス強化

## オープン課題

- 不正検知の具体ルール（悪意あるコード、リソース枯渇攻撃）
- カスタムデータセット持ち込みの可否・検証方法
- 公開チャレンジへの拡張（EvalAI統合、ランキング公式公開）
- Kubernetes移行時のストレージ戦略（共有ボリューム→S3/PVC等）
