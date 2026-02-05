# Research & Design Decisions

## Summary

- **Feature**: `streamlit-realtime-worker-logs`
- **Discovery Scope**: Extension（既存システムの拡張）
- **Key Findings**:
  - Workerは現在`subprocess.run()`を使用しており、完了後にのみログを保存している
  - `subprocess.Popen`でファイルハンドルを直接渡すことでリアルタイムストリーミングが可能
  - Streamlit UIは実行中ジョブのログ表示UIが欠落している
  - `st.fragment(run_every="5s")`で自動更新は実装済みだが、ログ取得は含まれていない

## Research Log

### Worker リアルタイムログ出力の実装方法

- **Context**: 現在`subprocess.run(capture_output=True)`で出力をキャプチャしているが、完了後にのみログファイルに保存される
- **Sources Consulted**:
  - Stack Overflow: Python subprocess.Popen real-time stdout/stderr streaming
  - Python公式ドキュメント: subprocess module
- **Findings**:
  - `subprocess.Popen(stdout=file_handle, stderr=subprocess.STDOUT)`でファイルに直接ストリーミング可能
  - ファイルハンドルを渡す方法が最もシンプルで、バッファリングなしでリアルタイム書き込み
  - `bufsize=1`（行バッファリング）と`text=True`で行単位のバッファリングが可能
  - タイムアウト処理には`process.wait(timeout=...)`を使用
- **Implications**:
  - `subprocess.run()`から`subprocess.Popen()`への変更が必要
  - ジョブ開始時にログファイルを作成し、stdout/stderrを直接書き込む
  - タイムアウト・異常終了処理のリファクタリングが必要

### Streamlit リアルタイム更新パターン

- **Context**: 既存の`st.fragment(run_every="5s")`パターンでステータスのみ更新、ログは未対応
- **Sources Consulted**:
  - Streamlit公式ドキュメント: st.fragment, Working with fragments
  - Streamlit tutorials: Start and stop streaming fragments
- **Findings**:
  - `run_every`パラメータで自動更新間隔を制御可能
  - Fragment内でのみ再実行されるため、フォーム入力状態は保持される
  - `run_every=None`で自動更新を停止可能（ジョブ完了時）
  - Streamlit 1.37.0以上で`run_every`パラメータをサポート
- **Implications**:
  - 既存の`_render_jobs`フラグメント内でログ取得を追加実装
  - 実行中ジョブの場合はログを自動取得・表示
  - UIコンポーネントの追加（ログ表示エリア、手動更新ボタン）

### API ログ取得エンドポイントの改善

- **Context**: 現在`FileNotFoundError`で404を返すが、実行中ジョブでは空ログが正常
- **Sources Consulted**: 既存コードベース分析
- **Findings**:
  - `storage.load_logs()`は`FileNotFoundError`を送出
  - APIエンドポイントはそれをそのまま500エラーとして返す（未処理）
  - 実行中ジョブでは空文字列を返すべき
- **Implications**:
  - `load_logs()`または APIエンドポイントでエラーハンドリング追加
  - 大きなログファイルのtail処理（最後の1000行）を実装

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| ファイルベースストリーミング | Popenでファイルに直接書き込み、APIでファイル読み取り | シンプル、既存アーキテクチャ活用 | 大量同時アクセス時のI/O | **選択** - 既存パターンと整合 |
| Redisストリーミング | Redis Pub/Subでログをストリーミング | リアルタイム性が高い | 複雑度増加、Redis依存 | 将来の拡張オプション |
| WebSocket | リアルタイム双方向通信 | 最もリアルタイム | Streamlit非対応、複雑 | 不採用 |

## Design Decisions

### Decision: subprocess.Popen + ファイル直接書き込み

- **Context**: リアルタイムでログを共有ストレージに出力する必要がある
- **Alternatives Considered**:
  1. `subprocess.run()` + 定期的なログコピー — 複雑、遅延あり
  2. `subprocess.Popen(stdout=PIPE)` + スレッドでファイル書き込み — 過度に複雑
  3. `subprocess.Popen(stdout=file_handle)` — シンプル、リアルタイム
- **Selected Approach**: Option 3 - ファイルハンドルを直接渡す
- **Rationale**: 最もシンプルで、追加のスレッド管理不要、OSレベルでバッファリング最小化
- **Trade-offs**: stderr/stdoutの混合出力になるが、ログ閲覧には十分
- **Follow-up**: `PYTHONUNBUFFERED=1`環境変数でPythonの出力バッファリングを無効化する必要があるか検証

### Decision: APIでのエラーハンドリング改善

- **Context**: 実行中ジョブのログ取得で404/500を返すのは不適切
- **Alternatives Considered**:
  1. StoragePort.load_logs()で空文字列を返す — 既存インターフェース変更
  2. APIエンドポイントでtry-exceptでハンドリング — 影響範囲が限定的
- **Selected Approach**: Option 2 - APIエンドポイントでエラーハンドリング
- **Rationale**: StoragePortインターフェースは「ファイルがない=エラー」が自然、APIで意味を解釈
- **Trade-offs**: エンドポイントごとにハンドリングが必要だが、今回は1箇所のみ

### Decision: Streamlit UIのログ表示追加

- **Context**: 実行中ジョブにログ表示UIがない
- **Alternatives Considered**:
  1. 新しいフラグメントを追加 — 構造変更大
  2. 既存`_render_jobs`内に条件分岐追加 — 最小限の変更
- **Selected Approach**: Option 2 - 既存フラグメント内に追加
- **Rationale**: 既存の5秒自動更新パターンを活用、UIフローの一貫性維持
- **Trade-offs**: `_render_jobs`関数が肥大化するが、適切な分割で対応可能

## Risks & Mitigations

- **Risk 1**: 大きなログファイルでメモリ/帯域消費 — tail処理（最後の1000行）で緩和
- **Risk 2**: ファイルI/O競合（Worker書き込み中にAPI読み取り） — OSレベルで安全、追加のロック不要
- **Risk 3**: Streamlit UIの頻繁な再描画でちらつき — `st.fragment`でフラグメント内のみ更新

## References

- [Streamlit st.fragment documentation](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
- [Start and stop a streaming fragment](https://docs.streamlit.io/develop/tutorials/execution-flow/start-and-stop-fragment-auto-reruns)
- [Python subprocess.Popen real-time streaming (Stack Overflow)](https://stackoverflow.com/questions/2331339/piping-output-of-subprocess-popen-to-files)
