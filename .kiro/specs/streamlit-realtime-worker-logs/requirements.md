# Requirements Document

## Introduction

LeadersBoardプラットフォームにおいて、Streamlit UI上でworkerプロセスのログをリアルタイムに表示する機能を開発する。この機能により、研究者および管理者はジョブ実行状況をより詳細に把握し、問題発生時の迅速な対応を可能にする。

## Requirements

### Requirement 1: Streamlit UIログ表示フィールド

**Objective:** 研究者として、Streamlit UIでジョブのログを確認できるログ表示フィールドがほしいので、実行状況を視覚的に把握するため

#### Acceptance Criteria

1. When ジョブが選択された場合, the Streamlit UI shall ジョブ詳細エリアに専用のログ表示フィールド（`st.text_area`または`st.code`コンポーネント）を常に表示する
2. When ジョブが実行中（`running`）の場合, the Streamlit UI shall ログ表示フィールドを展開状態で表示し、最新ログを表示する
3. Where ジョブが完了（`completed`/`failed`）している場合, the Streamlit UI shall ログ表示フィールドを折りたたみ可能なExpander内に表示する
4. The Streamlit UI shall ログ表示フィールドに十分な高さ（最低400px）を確保し、スクロール可能にする
5. If ログが空または取得できない場合, then the Streamlit UI shall 「ログはまだありません」または適切なメッセージを表示する

### Requirement 2: Workerリアルタイムログ出力

**Objective:** システムとして、Workerがジョブ実行中にリアルタイムでログを出力したいので、学習終了を待たずにログを確認できるようにするため

#### Acceptance Criteria

1. When Workerがジョブを実行する場合, the Worker shall `subprocess.Popen`を使用してサブプロセスを起動し、stdout/stderrをリアルタイムでキャプチャする
2. While ジョブが実行中の場合, the Worker shall サブプロセスの出力を数秒ごとまたは一定バイト数ごとに共有ストレージ（`/shared/logs/{job_id}.log`）に追記する
3. When サブプロセスが出力を生成した場合, the Worker shall 出力を即座にログファイルに書き込む（バッファリングを最小化）
4. If サブプロセスが異常終了した場合, then the Worker shall エラー情報をログファイルに追記してからステータスを更新する
5. The Worker shall ログ書き込み時にファイルロック等の排他制御を適切に行い、読み取り側との競合を防ぐ

### Requirement 3: API実行中ログ取得対応

**Objective:** 管理者として、実行中のジョブのログもAPI経由で取得したいので、リアルタイム監視を実現するため

#### Acceptance Criteria

1. When `GET /jobs/{job_id}/logs` が呼び出された場合, the API shall ジョブが実行中でも現時点のログファイル内容を返却する
2. If ログファイルが存在しない場合（ジョブ開始直後）, then the API shall 空文字列または「ログ生成中」を返却する（404エラーではなく）
3. Where ログファイルが非常に大きい場合, the API shall 最後の1000行のみを返却する（tail相当の動作）
4. The API shall ログ取得処理で発生したエラーを適切にログに記録する
5. If Workerがログファイルに書き込み中の場合, then the API shall 部分的なログでも取得可能とする

### Requirement 4: 自動更新によるリアルタイム表示

**Objective:** 研究者として、実行中のジョブのログが自動的に更新されてほしいので、手動リロードなしで進捗を追跡するため

#### Acceptance Criteria

1. When ジョブが実行中（`pending`/`running`）の場合, the Streamlit UI shall 5秒ごとにログを自動取得して表示を更新する
2. While 自動更新が実行中の場合, the Streamlit UI shall 「自動更新中...」のインジケータを表示する
3. When 新しいログが取得された場合, the Streamlit UI shall ログ表示フィールドを最新内容で更新し、自動スクロールで最新行を表示する
4. If 自動更新でログ取得に失敗した場合, then the Streamlit UI shall エラーメッセージを表示しつつ、最後に取得できたログを保持する
5. Where ジョブが完了（`completed`/`failed`）した場合, the Streamlit UI shall 自動更新を停止し、最終ログを表示する

### Requirement 5: UI/UX ユーザー体験

**Objective:** ユーザーとして、ログ表示が使いやすいUIを期待するので、効率的にログを閲覧するため

#### Acceptance Criteria

1. When ログが大量にある場合, the Streamlit UI shall ログ表示領域にスクロールバーを提供する
2. If ユーザーが手動でスクロールした場合, then the Streamlit UI shall 自動スクロールを一時停止し、ユーザーの閲覧位置を維持する
3. The Streamlit UI shall ログ表示領域に等幅フォントを使用し、ログの整形を維持する
4. Where エラーログ（`ERROR`、`Exception`等）が含まれている場合, the Streamlit UI shall 可能であれば視覚的に強調表示する
5. The Streamlit UI shall 手動更新ボタンを提供し、ユーザーが任意のタイミングでログを再取得できるようにする

### Requirement 6: パフォーマンスと安定性

**Objective:** システム管理者として、ログ表示機能がシステム全体のパフォーマンスに影響を与えないことを期待するので、安定したサービス提供のため

#### Acceptance Criteria

1. When ログ取得リクエストが頻発する場合, the システム shall 適切なレート制限を適用し、過負荷を防ぐ
2. The Worker shall ログ書き込みがジョブ実行のパフォーマンスに大きな影響を与えないようにする
3. While 複数のユーザーが同時にログを閲覧する場合, the Streamlit UI shall 各ユーザーのセッションを独立して管理する
4. The Streamlit UI shall ログ更新時に画面全体の再描画を避け、ログ領域のみを更新する（`st.fragment`使用）
5. Where ログファイルサイズが非常に大きい場合, the API shall メモリ使用量を抑制しつつログを返却する

### Requirement 7: セキュリティとアクセス制御

**Objective:** セキュリティ管理者として、ログアクセスが適切に制御されることを期待するので、情報漏洩を防止するため

#### Acceptance Criteria

1. When ログアクセスを要求する場合, the API shall Bearerトークン認証を必須とする
2. If 認証トークンが無効な場合, then the API shall 401エラーレスポンスを返却する
3. Where ユーザーが自分のジョブのログのみアクセスできる場合, the API shall ジョブの所有者を検証する
4. The Streamlit UI shall ログ取得時の認証トークンを安全に管理する
5. If ログに機密情報が含まれる場合, then the API shall ログ内容をフィルタリングして返却する
