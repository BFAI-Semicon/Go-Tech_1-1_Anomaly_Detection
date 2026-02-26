# リサーチ & 設計判断ログ

## Summary

- **Feature**: defect-location-visualization
- **Discovery Scope**: Extension
  （既存ヘキサゴナルアーキテクチャへの機能追加）
- **Key Findings**:
  - anomalib v2のImageVisualizerコールバックで
    評価時にHeatmap・Mask・Overlayが自動生成
  - 既存Workerはサブプロセスモデルで
    MLflow記録まで対応済み。
    可視化は収集・整理ステップとして追加可能
  - StoragePort拡張とAPIエンドポイント追加で、
    ヘキサゴナルアーキテクチャを維持したまま
    アーティファクトアクセスを実現可能

## Research Log

### anomalib v2 可視化API

- **Context**:
  Workerが可視化アーティファクトを生成する方式を
  検討するにあたり、
  anomalibの最新可視化APIを調査した
- **Sources Consulted**:
  - [Visualization in Anomalib v2][viz-guide]
  - [Engine Reference][engine-ref]
  - [Callbacks Reference][callbacks-ref]
- **Findings**:
  - `ImageVisualizer`はLightningコールバックで
    test/predictステップで自動的に可視化を生成
  - モデルへのVisualizer注入:
    `model = Patchcore(visualizer=ImageVisualizer())`
  - `visualize_anomaly_map()`:
    ピクセルレベル異常スコアのカラーマップ生成
  - `visualize_pred_mask()`:
    閾値処理後の2値マスク生成
  - `visualize_image_item()`:
    ImageItemオブジェクトの統合可視化
  - 可視化モジュールはexperimental
    （APIが変更される可能性あり）
- **Implications**:
  - ユーザーの投稿コードがanomalibのEngineを
    使用する場合、ImageVisualizerを設定すれば
    可視化は自動生成される
  - Workerは可視化の設定制御と
    成果物の収集・整理を担当する設計が最適
  - experimental APIのため、
    将来のanomalib更新でアダプター層の
    調整が必要になる可能性がある

[viz-guide]: https://anomalib.readthedocs.io/en/v2.0.0/markdown/guides/how_to/visualization/visualize_image.html
[engine-ref]: https://anomalib.readthedocs.io/en/v2.0.0/markdown/guides/reference/engine/index.html
[callbacks-ref]: https://anomalib.readthedocs.io/en/v2.0.0/markdown/guides/reference/callbacks/index.html

### anomalib 設定ファイル形式

- **Context**:
  config.yamlで可視化の有効・無効を
  制御する仕様を確認
- **Sources Consulted**:
  - [Anomalib Configuration][anomalib-config]
  - [Logging Tutorial][anomalib-logging]
  - anomalib.md（プロジェクト内調査資料）
- **Findings**:
  - v2ではVisualizerをモデルに直接渡す方式に
    変更されている
  - v1以前のconfig.yaml設定:
    `visualization.save_images`,
    `visualization.log_images`,
    `visualization.mode`
  - 本プラットフォーム独自の可視化設定セクションを
    定義し、Worker側で解釈する方式が適切
- **Implications**:
  - config.yamlに `visualization` セクションを
    定義（`enabled`, `types` フィールド）
  - Worker（VisualizationConfig）が解析し、
    サブプロセス実行後の収集・整理に反映する

[anomalib-config]: https://anomalib.readthedocs.io/en/v0.3.4/api/anomalib/config/config/index.html
[anomalib-logging]: https://anomalib.readthedocs.io/en/v0.3.7/tutorials/logging.html

### anomalib 出力ディレクトリ構造

- **Context**:
  可視化アーティファクトの標準ディレクトリ構造を
  決定するため、
  anomalibのデフォルト出力構造を調査
- **Sources Consulted**:
  - anomalib.md セクション4
- **Findings**:
  - anomalibのデフォルト出力構造:
    `results/<model>/<dataset>/images/`
  - CSV出力:
    `image_predictions.csv`,
    `pixel_predictions.csv`
  - モデル系統によらず同一構造で出力される
- **Implications**:
  - 本プラットフォームの標準構造として
    `<artifact_root>/<job_id>/visualizations/`
    を採用
  - anomalibの出力をこの構造に正規化する
    VisualizationCollectorを設計する
  - ファイル命名規則:
    `{original_image_name}_{type}.png`
    （Req 2.3準拠）

### 既存アーキテクチャのアーティファクト処理

- **Context**:
  既存Worker・API・UI間の
  アーティファクト処理パターンを把握し、
  拡張方針を決定
- **Sources Consulted**:
  - `src/worker/job_worker.py`
  - `src/ports/tracking_port.py`
  - `src/adapters/mlflow_tracking_adapter.py`
  - `src/ports/storage_port.py`
  - `src/adapters/filesystem_storage_adapter.py`
  - `src/api/jobs.py`
- **Findings**:
  - Worker: `_record_metrics()` で
    `tracking.log_artifact(str(output_dir))`
    を呼び出し、output_dir全体をMLflowに記録
  - StoragePort:
    提出ファイル・ログの読み書きに特化。
    アーティファクトの個別アクセスは未実装
  - API: `/jobs/{job_id}/results` は
    `run_id` とMLflowリンクのみ返却。
    アーティファクト実体の配信機能なし
  - FileSystemStorageAdapter:
    `submissions_root`, `logs_root` を受け取る。
    `artifacts_root` は未管理
- **Implications**:
  - `tracking.log_artifact(output_dir)` は
    visualizationsサブディレクトリも
    含めて自動記録する。TrackingPort変更不要
  - StoragePortに `list_artifacts()` と
    `load_artifact_file()` を追加
  - FileSystemStorageAdapterに
    `artifacts_root` パラメータを追加
  - API層に可視化専用エンドポイントを追加

### Streamlit UI 可視化表示パターン

- **Context**:
  Streamlit UIでの画像表示・比較パターンを調査
- **Sources Consulted**:
  - `src/streamlit/app.py`（既存UI実装）
  - Streamlit API:
    `st.image`, `st.columns`, `st.expander`
- **Findings**:
  - 既存UIは `st.expander` でログ折りたたみ
  - `st.columns` で2列レイアウト
  - `st.image` で画像表示が可能
    （URL、バイト列、PIL Image対応）
  - Fragment自動更新パターンを使用
- **Implications**:
  - 4列レイアウトを `st.columns(4)` で実現
    （Original / Heatmap / Mask / Overlay）
  - 完了済みジョブのみ可視化セクションを表示
  - API経由で画像バイト列を取得し
    `st.image` で表示
  - サムネイル一覧は `st.expander` 内に配置

## Architecture Pattern Evaluation

|         Option         |   Strengths    |   Risks    |
| ---------------------- | -------------- | ---------- |
| Worker後処理型（採用） | 既存モデル維持 | コード依存 |
| Worker再実行型         | 完全制御       | GPU倍増    |
| 設定注入型             | 変更不要       | 互換性Risk |

- **Worker後処理型**: サブプロセス完了後に
  Workerが出力ディレクトリから収集・整理する。
  既存サブプロセスモデルを維持でき変更が最小限。
  ユーザーコードが可視化を出力する前提
- **Worker再実行型**: Worker側でモデルをロードし
  可視化を再生成する。Workerが完全制御できるが、
  評価の二重実行でGPU時間が倍増
- **設定注入型**: Workerがconfig.yamlを動的に
  書き換えて可視化を有効化する。
  config形式の互換性リスクあり

## Design Decisions

### Decision: Worker後処理型の採用

- **Context**:
  Workerが可視化アーティファクトを「生成」する
  方式の選択
- **Alternatives Considered**:
  1. Worker再実行型 — モデルチェックポイントを
     読み込み可視化を再生成
  2. 設定注入型 — config.yamlを動的書き換え
  3. Worker後処理型 — サブプロセス生成物を
     収集・整理・記録
- **Selected Approach**: Worker後処理型
- **Rationale**:
  - 既存のサブプロセス分離モデルを維持
  - GPU時間の二重消費を回避
  - anomalibのImageVisualizerが評価と同時に
    可視化を生成するため追加コスト最小
  - VisualizationCollectorをWorker内部
    サービスとして実装し原則を維持
- **Trade-offs**:
  - ユーザーコードがanomalibの可視化を
    正しく設定する前提
  - 可視化が生成されない場合の
    フォールバックが限定的
  - anomalib出力構造への依存
- **Follow-up**:
  - ユーザー向けドキュメントで
    可視化出力の要件を明記
  - anomalibバージョンアップ時の
    アダプター互換性テスト

### Decision: StoragePort拡張

- **Context**:
  API経由で可視化画像を配信する方式の決定
- **Alternatives Considered**:
  1. MLflow API経由 — Tracking Serverの
     artifacts APIを透過的に利用
  2. 直接ファイルサーブ — Nginx経由で
     `/shared/artifacts/` を静的配信
  3. StoragePort拡張 — 既存ポート・
     アダプターパターンにメソッド追加
- **Selected Approach**: StoragePort拡張
- **Rationale**:
  - ヘキサゴナルアーキテクチャの一貫性維持
  - セキュリティ制御を一元管理
  - テスタビリティ（モック検証可能）
  - 既存FastAPI依存性注入に統合可能
- **Trade-offs**:
  - API経由のため大量画像取得時のレイテンシ
  - MLflow APIの方がアーティファクト検索が豊富
- **Follow-up**:
  大量画像のパフォーマンス計測と
  ページネーション実装の検討

## Risks and Mitigations

- **ユーザーコードが可視化を出力しないリスク** —
  グレースフル処理（ログ記録 + メトリクス継続、
  UIで「可視化結果なし」表示）
- **anomalib API変更リスク（experimental）** —
  アダプター層で抽象化し影響範囲を限定
- **大量テスト画像によるディスク容量圧迫** —
  可視化無効化設定 (6.2) で制御可能。
  将来的にアーティファクト保持期間ポリシー検討
- **パストラバーサルセキュリティリスク** —
  既存 `_validate_path` パターンを踏襲し
  アーティファクトアクセスでもパス検証実施

## References

- [Anomalib v2 Visualization Guide][viz-guide] —
  可視化APIの使用方法・コンポーネント構成
- [Anomalib v2 Engine Reference][engine-ref] —
  Engineクラスの設定・実行パラメータ
- [Anomalib v2 Callbacks Reference][callbacks-ref]
  — ImageVisualizerコールバックの仕様
- anomalib.md（プロジェクト内調査資料） —
  モデル系統別可視化特性・出力構造の詳細
