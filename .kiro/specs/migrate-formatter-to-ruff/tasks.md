# Implementation Plan

## Overview

blackからruff formatへの移行を5フェーズで実施する。各フェーズは前のフェーズに依存するため、順次実行する。

## Tasks

### Phase 1: 設定追加

- [ ] 1. pyproject.tomlのruff format設定を追加
  - `[tool.ruff.format]`セクションを追加
  - `quote-style = "double"`, `indent-style = "space"` 等を設定
  - _Requirements: 1.1, 1.2_

- [ ] 2. pyproject.tomlからblack/isort設定を削除
  - `[tool.black]`セクションを削除
  - `[tool.isort]`セクションを削除
  - _Requirements: 6.4, 6.5_

- [ ] 3. ruff format設定の動作確認
  - `ruff format --check .`を実行して設定が有効か確認
  - エラーがあれば修正
  - _Requirements: 1.3, 1.4_

### Phase 2: 全ファイルフォーマット

- [ ] 4. 全Pythonファイルをruff formatで再フォーマット
  - `cd LeadersBoard && ruff format .`を実行
  - 差分を確認し、blackとの差異がないことを検証
  - _Requirements: 1.3, 1.5_

### Phase 3: CI/ワークフロー更新

- [ ] 5. ci.ymlにruff format checkを追加 (P)
  - `ruff check .`の後に`ruff format --check .`を追加
  - フォーマット違反時にビルドが失敗することを確認
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 6. VSCode tasks.jsonを更新 (P)
  - 「Ruff Check」タスクに`ruff format --check`を追加
  - 「Ruff Fix」タスクに`ruff format`を追加
  - _Requirements: 4.3, 4.4_

### Phase 4: ドキュメント更新

- [ ] 7. tech.mdのCode Qualityセクションを更新 (P)
  - Formatter記述を`ruff format`に変更
  - Import Order記述を`ruff`（`I`ルール）に変更
  - _Requirements: 5.1_

- [ ] 8. tech.mdのCommon Commandsセクションを更新 (P)
  - `black . && isort .`を`ruff format .`に変更
  - `ruff check . && black --check .`を`ruff check . && ruff format --check .`に変更
  - _Requirements: 5.2_

### Phase 5: 依存削除

- [ ] 9. requirements-dev.txtからblack/isortを削除
  - `black>=24.10.0`を削除
  - `isort>=5.13.0`を削除
  - `ruff>=0.8.0`が残っていることを確認
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 10. 最終検証
  - `pip install -r requirements-dev.txt`で依存関係をクリーンインストール
  - `ruff check . && ruff format --check .`でエラーがないことを確認
  - _Requirements: 1.4, 3.2_

## Parallel Execution Notes

- タスク5-8は並列実行可能（`(P)`マーク）
- Phase 1-2は順次実行が必須（設定変更→フォーマット適用の順序）
- Phase 5はPhase 3-4完了後に実行（CI/ドキュメントが更新されてから依存削除）

## Validation Checkpoints

- Phase 1完了後: `ruff format --check .`が動作すること
- Phase 2完了後: 全ファイルがフォーマット済みであること
- Phase 3完了後: CIが`ruff format --check`を実行すること
- Phase 5完了後: black/isortなしで環境が動作すること
