# Research & Design Decisions

## Summary

- **Feature**: `migrate-formatter-to-ruff`
- **Discovery Scope**: Extension（既存システムへの機能拡張）
- **Key Findings**:
  - pyproject.tomlに既に`[tool.ruff]`と`[tool.ruff.lint.isort]`が設定済み
  - `[tool.black]`と`[tool.isort]`セクションが残存しており削除が必要
  - CI/CDパイプラインにフォーマットチェックが未実装

## Research Log

### 現在の設定状況

- **Context**: blackからruffへの移行に必要な変更範囲を特定
- **Sources Consulted**: `pyproject.toml`, `requirements-dev.txt`, `ci.yml`, `tasks.json`, `tech.md`
- **Findings**:
  - `[tool.ruff]`: `line-length = 100`, `target-version = "py313"` 設定済み
  - `[tool.ruff.lint]`: `I`（isort）ルール有効化済み
  - `[tool.ruff.lint.isort]`: `known-first-party = ["src"]` 設定済み
  - `[tool.black]`: `target-version = ["py313"]`, `line-length = 100` が残存
  - `[tool.isort]`: `profile = "black"`, `line_length = 100` が残存
  - `requirements-dev.txt`: `black>=24.10.0`, `isort>=5.13.0` が残存
- **Implications**: ruffのlint設定は完了済み。format設定の追加とblack/isort関連の削除が主な作業

### Ruff Formatter設定オプション

- **Context**: ruff formatの設定オプションを確認
- **Sources Consulted**: [Ruff公式ドキュメント](https://docs.astral.sh/ruff/configuration/)
- **Findings**:
  - `[tool.ruff.format]`セクションでフォーマット設定を定義
  - `quote-style = "double"`: ダブルクォート使用（black互換）
  - `indent-style = "space"`: スペースインデント（black互換）
  - `skip-magic-trailing-comma = false`: マジックトレイリングカンマを尊重
  - `line-ending = "auto"`: 行末を自動検出
  - `docstring-code-format = false`: docstring内コードの自動フォーマット（デフォルト無効）
- **Implications**: デフォルト設定がblack互換のため、明示的な設定は最小限で済む

### CI/CDパイプライン

- **Context**: フォーマットチェックの追加方法を確認
- **Sources Consulted**: `.github/workflows/ci.yml`
- **Findings**:
  - 現在は`ruff check .`のみ実行
  - `ruff format --check .`を追加することでフォーマット違反を検出可能
  - 違反時は非ゼロ終了コードを返す
- **Implications**: CIステップに`ruff format --check .`を追加

### VSCodeタスク

- **Context**: 開発ワークフローの更新方法を確認
- **Sources Consulted**: `.vscode/tasks.json`
- **Findings**:
  - 「Ruff Check」: `ruff check .`のみ
  - 「Ruff Fix」: `ruff check --fix .`のみ
  - フォーマットコマンドが未統合
- **Implications**: 両タスクにformat系コマンドを追加

## Design Decisions

### Decision: Ruff Formatデフォルト設定の採用

- **Context**: blackと同等のフォーマットスタイルを維持する必要がある
- **Alternatives Considered**:
  1. 明示的に全オプションを設定
  2. デフォルト設定を採用（必要に応じてオーバーライド）
- **Selected Approach**: デフォルト設定を採用
- **Rationale**: ruff formatはblack互換がデフォルトであり、既存の`line-length = 100`設定が継承される
- **Trade-offs**: 明示性は低下するが、設定の簡潔さと保守性が向上
- **Follow-up**: 移行後にフォーマット結果を確認し、必要に応じて微調整

### Decision: black/isort依存の完全削除

- **Context**: ツールチェーンの簡素化と依存関係の削減
- **Alternatives Considered**:
  1. black/isortを残してruffと併用
  2. black/isortを完全削除してruffに一本化
- **Selected Approach**: 完全削除してruffに一本化
- **Rationale**: ruffがblack/isortの機能を完全にカバーしており、重複ツールは保守コストを増加させる
- **Trade-offs**: 一時的な移行コストが発生するが、長期的には保守性が向上
- **Follow-up**: 移行後の動作確認、チームへの周知

## Risks & Mitigations

- **フォーマット差異**: black/ruff間の微細な差異 → 初回実行時に全ファイルを再フォーマット
- **CI失敗**: 移行直後のCIエラー → PRで事前にフォーマット適用してからマージ
- **開発者混乱**: コマンド変更による混乱 → ドキュメント更新と周知

## References

- [Ruff Configuration](https://docs.astral.sh/ruff/configuration/) — 公式設定ドキュメント
- [Ruff Formatter](https://docs.astral.sh/ruff/formatter/) — フォーマッター機能の詳細
