# 調査・設計判断記録

---

**目的**: 発見事項、アーキテクチャ調査、技術設計の根拠を記録する

**使用方法**:

- 発見フェーズでの調査活動と結果を記録
- `design.md`に記載するには詳細すぎる設計判断のトレードオフを文書化
- 将来の監査や再利用のための参考資料と証拠を提供

---

## 概要

- **機能**: `sequential-file-upload`
- **発見範囲**: Extension（既存システムの拡張）
- **主要な発見**:
  - 既存の`POST /submissions`は複数ファイルを一括受信する設計
  - `FileSystemStorageAdapter`は追加保存機能を持たず、全ファイルを一度に保存
  - `EnqueueJob`はsubmissionメタデータから参照するが、ファイル存在確認は行わない
  - Streamlit UIは`submit_submission()`で複数ファイルを1リクエストで送信

## 調査ログ

### 既存のファイルアップロード実装分析

- **背景**: 順次アップロードを実装するため、既存の一括アップロード方式を理解する必要がある
- **調査対象**: `src/api/submissions.py`, `src/domain/create_submission.py`,
  `src/adapters/filesystem_storage_adapter.py`
- **発見**:
  - `POST /submissions`エンドポイントは`list[UploadFile]`を受け取る
  - `CreateSubmission.execute()`は`Iterable[BinaryIO]`を受け取り、`storage.save()`を1回呼び出す
  - `FileSystemStorageAdapter.save()`は全ファイルをループで保存し、`metadata.json`に記録
  - ファイルリストは`metadata.json`の`files`フィールドに保存される
- **影響**:
  - 新しいエンドポイント`POST /submissions/{submission_id}/files`が必要
  - `StoragePort`に追加保存メソッドが必要
  - `metadata.json`のfiles配列を更新する機能が必要

### ファイル存在確認とジョブ投入の関係

- **背景**: 順次アップロードでは、全ファイルアップロード完了後にジョブを投入する必要がある
- **調査対象**: `src/domain/enqueue_job.py`
- **発見**:
  - `EnqueueJob.execute()`はsubmission存在確認（`storage.exists()`）のみ実行
  - entrypoint/config_fileファイルの存在確認は行われていない
  - `StoragePort.validate_entrypoint()`メソッドが存在するが、`EnqueueJob`では使用されていない
- **影響**:
  - ジョブ投入前にentrypoint/config_fileの存在を検証する必要がある（要件5）
  - `EnqueueJob`に完全性検証ロジックを追加するか、新しいユースケースを作成

### Streamlit UIのアップロードフロー

- **背景**: Streamlit UIを順次アップロード対応に変更する必要がある
- **調査対象**: `src/streamlit/app.py`
- **発見**:
  - `submit_submission()`は`files`パラメータに複数のファイルタプルを受け取る
  - `requests.post()`で`files=[("files", f) for f in files]`として一括送信
  - アップロード成功後に`create_job()`を呼び出してジョブを投入
  - セッションステートでジョブ一覧を管理
- **影響**:
  - `submit_submission()`を分割：最初のファイルと追加ファイル
  - 新しい関数`add_submission_file()`が必要
  - 進捗表示のためのステート管理が必要
  - エラーハンドリングとリトライロジックを実装

### ファイルサイズ制限の確認

- **背景**: 要件では100MB制限だが、既存実装では異なる制限値
- **調査対象**: `src/domain/create_submission.py`
- **発見**:
  - `MAX_FILE_SIZE = 500 * 1024 * 1024`（500MB）として定義されている
  - 各ファイルの合計サイズではなく、個別ファイルサイズをチェック
- **影響**:
  - 既存の500MB制限と新要件の100MB制限の整合性を確認
  - 新しいエンドポイントでも同じ検証ロジックを再利用
  - ドキュメントと実装の一貫性を保つ

## アーキテクチャパターン評価

| オプション             | 説明                          | 強み               | リスク・制約         | 備考   |
| ---------------------- | ----------------------------- | ------------------ | -------------------- | ------ |
| 新規ユースケース追加   | `AddSubmissionFile`を新規作成 | 影響最小、単一責任 | ロジック重複可能性   | 推奨   |
| `CreateSubmission`拡張 | 既存に統合                    | 重複削減           | 影響リスク、責任違反 | 非推奨 |
| `StoragePort`直接利用  | API層から直接呼び出し         | シンプル           | テスタビリティ低下   | 非推奨 |

**選択**: 新規ユースケース追加（`AddSubmissionFile`）

## 設計判断

### 判断: ファイル追加用の新規ユースケース作成

- **背景**: 既存のsubmissionに対してファイルを1つずつ追加する機能が必要
- **検討した代替案**:
  1. `CreateSubmission`を拡張して部分的なファイル追加をサポート
  2. 新しいユースケース`AddSubmissionFile`を作成
  3. API層で直接`StoragePort`を呼び出す
- **選択したアプローチ**: 新しいユースケース`AddSubmissionFile`を作成
- **根拠**:
  - Clean-lite設計の単一責任原則に従う
  - 既存の`CreateSubmission`への影響を最小化
  - テスタビリティを維持（ユニットテストが容易）
  - 将来的な拡張性（バリデーションルールの独立管理）
- **トレードオフ**:
  - **利点**: 既存コードの安定性、明確な責任分離
  - **欠点**: 若干のコード重複（バリデーションロジック）
- **フォローアップ**: バリデーションロジックの共通化を検討（将来的なリファクタリング）

### 判断: `StoragePort`にファイル追加メソッドを追加

- **背景**: 既存の`save()`メソッドは全ファイルを一度に保存する設計
- **検討した代替案**:
  1. `save()`メソッドを拡張して追加モードをサポート
  2. 新しいメソッド`add_file()`を追加
  3. メタデータのみ更新する`update_metadata()`を追加
- **選択したアプローチ**: 新しいメソッド`add_file()`と`list_files()`を追加
- **根拠**:
  - インタフェース分離原則に従う
  - 既存の`save()`の動作を変更しない（後方互換性）
  - 明示的なメソッド名で意図が明確
- **トレードオフ**:
  - **利点**: 既存機能への影響なし、明確なAPI
  - **欠点**: ポートインタフェースの拡張（全アダプタで実装必要）
- **フォローアップ**: 他のアダプタ（S3等）も将来的に対応可能な設計

### 判断: ジョブ投入時の完全性検証を`EnqueueJob`に追加

- **背景**: 順次アップロードでは、全必須ファイルが揃ってからジョブを投入する必要がある
- **検討した代替案**:
  1. `EnqueueJob`に検証ロジックを追加
  2. 新しいユースケース`ValidateSubmission`を作成
  3. API層で検証を実行
- **選択したアプローチ**: `EnqueueJob`に検証ロジックを追加
- **根拠**:
  - ジョブ投入の前提条件としてsubmissionの完全性を保証
  - ドメインロジックとしての適切な配置
  - 既存の`storage.validate_entrypoint()`メソッドを活用
- **トレードオフ**:
  - **利点**: ビジネスルールの一貫性、テスト容易性
  - **欠点**: `EnqueueJob`の責任が若干増加
- **フォローアップ**: エラーメッセージに不足ファイル名を含める

### 判断: Streamlit UIでの自動リトライ実装

- **背景**: 一時的なネットワークエラーで全体が失敗しないようにする（要件6）
- **検討した代替案**:
  1. Streamlit UI側でリトライロジックを実装
  2. API側でリトライを実装
  3. リトライなし（ユーザーに再送信を依頼）
- **選択したアプローチ**: Streamlit UI側でリトライロジックを実装
- **根拠**:
  - クライアント側の責任として適切
  - API側は冪等性を保つシンプルな実装
  - ユーザーエクスペリエンスの向上
- **トレードオフ**:
  - **利点**: ネットワーク障害耐性、ユーザー体験向上
  - **欠点**: UI側のロジックが若干複雑化
- **フォローアップ**: リトライ中の進捗表示を実装

## リスクと対策

- **リスク1: アップロード中のWorker実行開始**
  - 対策: `EnqueueJob`でファイル存在確認を必須化、
    クライアント側で全ファイル完了後にジョブ投入
- **リスク2: metadata.json更新時の競合**
  - 対策: ファイルシステムレベルのatomic write、順次アップロード（並列なし）
- **リスク3: 部分的アップロード後のゴミデータ**
  - 対策: submissionのTTL設定（将来）、管理者向けクリーンアップツール（将来）
- **リスク4: 既存一括アップロードとの互換性**
  - 対策: 既存エンドポイントを維持、metadata.json形式を統一、Worker側の変更不要

## 参照資料

- [FastAPI File Uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
  — マルチパートファイルアップロードの公式ドキュメント
- [Streamlit File Uploader](https://docs.streamlit.io/library/api-reference/widgets/st.file_uploader)
  — Streamlitのファイルアップロードウィジェット
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
  — 型安全性のためのPython公式ドキュメント
- Clean Architecture（Robert C. Martin）
  — ドメイン駆動設計とポート/アダプタパターンの原則
