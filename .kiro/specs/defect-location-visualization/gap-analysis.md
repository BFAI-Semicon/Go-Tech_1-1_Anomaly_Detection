# ギャップ分析: 欠陥箇所の可視化機能

## 1. 現状の把握

### 1.1 アーキテクチャ概要

LeadersBoardは Clean-lite設計（ポート/アダプタ）を採用しており、以下のレイヤーで構成される。

| レイヤー  | 場所             | 役割                                      |
| --------- | ---------------- | ----------------------------------------- |
| Domain    | `src/domain/`    | ユースケース（CreateSubmission 等）       |
| Ports     | `src/ports/`     | 抽象インターフェース（5種）               |
| Adapters  | `src/adapters/`  | 具体実装（Redis, MLflow, FileSystem）     |
| API       | `src/api/`       | FastAPI エンドポイント                    |
| Worker    | `src/worker/`    | ジョブ実行・MLflow記録                    |
| Streamlit | `src/streamlit/` | Web UI（Thin Client）                     |

### 1.2 現在のジョブ実行フロー

```text
投稿者コード（anomalib） → metrics.json 出力
                              ↓
Worker: _load_metrics() → _record_metrics() → MLflow記録
                              ↓
                    log_artifact(output_dir全体)
```

**重要な設計前提**: 投稿者のコードが anomalib を実行し成果物を出力する。
Worker はメトリクス収集・MLflow記録のオーケストレーター。

### 1.3 既存コンポーネントの状態

#### Worker (`src/worker/job_worker.py`)

- `execute_job()` → `_execute_subprocess()` → `_load_metrics()` → `_record_metrics()`
- サブプロセスに `--output <artifact_root>/<job_id>` を渡す
- `_record_metrics()` 内で `tracking.log_artifact(str(output_dir))` を実行
- **可視化関連処理: 未実装**

#### TrackingPort / MLflowTrackingAdapter

- `log_artifact(local_path: str)` メソッドが存在
- ディレクトリを渡すとディレクトリ全体を MLflow にアップロード
- **アーティファクト一覧取得やダウンロードのメソッド: なし**

#### StoragePort / FileSystemStorageAdapter

- 提出ファイル保存・ログ読み込みに対応
- **アーティファクトファイルの一覧取得メソッド: なし**
- `load_logs()` は tail_lines 対応済み

#### API (`src/api/jobs.py`)

- `GET /jobs/{job_id}/results` → MLflow UI/REST リンクのみ返却
- **アーティファクト一覧・ダウンロードエンドポイント: なし**

#### Streamlit UI (`src/streamlit/app.py`)

- ジョブ一覧、ステータス、ログ、MLflow リンクを表示
- `st.fragment(run_every="5s")` による自動更新
- **画像/可視化アーティファクトの表示: 未実装**

#### デモコード (`demo_anomalib/`, `demo_anomalib2/`)

- `metrics.json` を生成（params, metrics, performance）
- config.yaml に `visualization` セクション: **なし**
- anomalib の可視化出力: **未有効化**

---

## 2. 要件-アセット マップ

### Req 1: アーティファクト生成

- 必要: anomalib 可視化有効化
- 既存: anomalib が標準で可視化出力可能
- **Missing**: デモ config に visualization 設定なし。
  投稿者コード側の責任範囲の明確化が必要

### Req 2: アーティファクト保存

- 必要: `visualizations/` への整理・MLflow 記録
- 既存: `log_artifact(output_dir)` で出力ディレクトリ全体を記録済み
- **Missing**: 可視化ディレクトリの標準化。
  anomalib 出力構造と Worker 期待構造の整合

### Req 3: UI表示

- 必要: Streamlit での画像表示
- 既存: `st.image()` API は Streamlit 標準機能
- **Missing**: 画像取得 API、表示コンポーネント、レイアウト全体

### Req 4: 取得API

- 必要: アーティファクト一覧・ダウンロード
- 既存: FastAPI + StoragePort
- **Missing**: StoragePort にアーティファクト一覧メソッドなし。
  新規エンドポイント2つ必要

### Req 5: CSV出力

- 必要: `image_predictions.csv` / `pixel_predictions.csv`
- 既存: anomalib が標準で CSV 出力可能
- **Missing**: デモ config で CSV 出力未有効化。
  API からの CSV ダウンロード機能

### Req 6: 可視化設定

- 必要: config.yaml 経由の制御
- 既存: anomalib config で `visualization` 設定可能
- **Missing**: Worker 側での設定解釈。デフォルト有効化の仕組み

---

## 3. 技術的な課題と未知数

### 3.1 anomalib の可視化出力ディレクトリ構造 (Research Needed)

- anomalib v1.x / v2.x で出力構造が異なる可能性
- `anomalib.md` では `results/<model>/<dataset>/images/` だが、
  `--output` 引数指定時の出力先パスの挙動を確認が必要
- 投稿者コードのエントリポイント実装によっても変動する

### 3.2 画像データの配信方式 (Research Needed)

- 選択肢 A: ファイルシステムから直接 `FileResponse` で返却
- 選択肢 B: MLflow REST API 経由でアーティファクト取得
- 選択肢 C: Streamlit から共有ボリュームに直接アクセス
- パフォーマンス・セキュリティの観点で要検討

### 3.3 可視化生成の責任境界

- 現状: 投稿者コードが全成果物を出力（metrics.json 含む）
- 問題: 可視化は投稿者コード側で有効化が必要（Worker 単独では制御困難）
- 選択肢: 投稿者コード規約として定義 / Worker がポスト処理で補完

---

## 4. 実装アプローチオプション

### Option A: 既存コンポーネント拡張（投稿者コード責任モデル）

**概要**: 可視化生成は投稿者コードの責任。Worker は収集・記録のみ拡張。

**変更対象**:

- `StoragePort` に `list_artifacts()`, `get_artifact_path()` 追加
- `FileSystemStorageAdapter` に上記の実装追加
- `src/api/jobs.py` にアーティファクト一覧・取得エンドポイント追加
- `src/streamlit/app.py` に可視化表示セクション追加
- `demo_anomalib*/config.yaml` に visualization 設定追加
- `docs/api.md` に投稿者コード規約（可視化出力ディレクトリ構造）追加

**Trade-offs**:

- 良い点: 既存アーキテクチャとの整合性が高い。投稿者の自由度が高い
- 良い点: Worker の変更が最小限（可視化ディレクトリの検出のみ）
- 悪い点: 投稿者が正しい構造で出力しない場合、可視化が機能しない
- 悪い点: anomalib 以外のフレームワーク使用時の互換性が不明

### Option B: 新規コンポーネント作成（Worker ポスト処理モデル）

**概要**: Worker がサブプロセス実行後に可視化アーティファクトを収集・整理する
新しいドメインユースケース `CollectVisualizations` を追加。

**新規作成**:

- `src/domain/collect_visualizations.py`: 可視化収集ユースケース
- `src/ports/artifact_port.py`: アーティファクト管理ポート
- `src/adapters/filesystem_artifact_adapter.py`: ファイルシステムアーティファクトアダプタ
- `src/api/artifacts.py`: アーティファクト API ルーター
- Streamlit 可視化表示コンポーネント

**Trade-offs**:

- 良い点: 投稿者コードのディレクトリ構造に依存しない（Worker が正規化）
- 良い点: 関心の分離が明確
- 悪い点: ファイル数が多く、設計・実装コストが大きい
- 悪い点: anomalib の出力構造への依存が Worker 側に移動するだけ

### Option C: ハイブリッド（推奨）

**概要**: 投稿者コード規約 + Worker の軽量ポスト処理 + 新規 API/UI

**Phase 1（MVP）**:

- 投稿者コード規約: `{output}/visualizations/` に可視化画像を配置
- Worker: `execute_job()` に可視化ディレクトリ検出ロジック追加（軽量）
- StoragePort 拡張: `list_artifacts()`, `get_artifact_path()` 追加
- API: `/jobs/{job_id}/artifacts`, `/jobs/{job_id}/artifacts/{filename}` 追加
- Streamlit: 完了ジョブの可視化サムネイル表示

**Phase 2（拡張）**:

- Worker ポスト処理: anomalib 標準出力構造を `visualizations/` に正規化
- Streamlit: 比較レイアウト、拡大表示
- CSV ダウンロード API

**Trade-offs**:

- 良い点: MVP を素早く提供し、段階的に拡張可能
- 良い点: 既存パターンを活用しつつ、新規コンポーネントの範囲を限定
- 悪い点: Phase 1 と Phase 2 で投稿者コード規約が変化する可能性
- 良い点: リスクを分散できる

---

## 5. 実装複雑度とリスク

| 項目           | 工数            | リスク       | 根拠                                |
| -------------- | --------------- | ------------ | ----------------------------------- |
| 全体           | **M（3-7日）**  | **Medium**   | 新規 API/UI + ポート拡張            |
| Req 1: 生成    | S               | Low          | anomalib config + デモ更新のみ      |
| Req 2: 保存    | S               | Low          | 既存 log_artifact() で記録済み      |
| Req 3: UI表示  | M               | Medium       | 新規 Streamlit + 画像配信方式検討   |
| Req 4: API     | M               | Low          | 既存パターンに沿って実装可能        |
| Req 5: CSV     | S               | Low          | anomalib config + ファイル DL       |
| Req 6: 設定    | S               | Low          | config.yaml 設定追加                |

---

## 6. 設計フェーズへの推奨事項

### 推奨アプローチ

**Option C（ハイブリッド）** を推奨。理由:

1. 既存の Clean-lite 設計との整合性を保ちながら最小限の新規コンポーネントで実現可能
2. 投稿者コード規約を先に定義することで、Worker 側の複雑さを抑制
3. Phase 分割により MVP を早期に提供可能

### 設計フェーズで解決すべき事項

1. **anomalib 可視化出力パスの確定**: `--output` 引数指定時に anomalib がどのパスに可視化画像を出力するか実機検証
2. **画像配信方式の決定**: ファイルシステム直接 vs MLflow REST vs 共有ボリューム
3. **投稿者コード規約の具体化**: 可視化出力の期待ディレクトリ構造・ファイル命名規則
4. **StoragePort 拡張 vs ArtifactPort 新設**: 責務分離の粒度を決定
5. **Streamlit UI レイアウト設計**: サムネイル一覧・比較表示の具体的な UI 構成
