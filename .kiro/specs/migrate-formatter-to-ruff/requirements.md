# Requirements Document

## Introduction

本ドキュメントは、Pythonコードフォーマッターをblackからruffへ移行する要件を定義します。ruffはRust製の高速なPythonリンター/フォーマッターであり、black互換のフォーマット機能とisort互換のインポートソート機能を統合しています。この移行により、ツールチェーンの簡素化、CI/CD実行時間の短縮、開発者体験の向上を実現します。

## Requirements

### Requirement 1: Ruffフォーマッター設定

**Objective:** 開発者として、ruffによるコードフォーマットを使用したい。これにより、blackと同等のフォーマット品質を維持しながらツールチェーンを簡素化できる。

#### Acceptance Criteria 1

1. The ruff formatter shall フォーマット設定をpyproject.tomlの`[tool.ruff.format]`セクションで定義する
2. The ruff formatter shall blackと同等のコードスタイル（行長、クォートスタイル等）を維持する
3. When `ruff format .`を実行した場合, the ruff formatter shall プロジェクト内の全Pythonファイルをフォーマットする
4. When `ruff format --check .`を実行した場合, the ruff formatter shall フォーマット違反があれば非ゼロ終了コードを返す
5. The ruff formatter shall `.py`ファイルのみをフォーマット対象とする

### Requirement 2: インポートソート統合

**Objective:** 開発者として、ruffによるインポートソートを使用したい。これにより、isortを別途実行する必要がなくなる。

#### Acceptance Criteria 2

1. The ruff linter shall `I`（isort）ルールを有効化してインポートソートを検証する
2. When `ruff check --fix .`を実行した場合, the ruff linter shall インポート順序の自動修正を行う
3. The ruff configuration shall 現在のisort設定と同等のインポート順序ルールを適用する
4. The ruff linter shall 標準ライブラリ、サードパーティ、プロジェクト内インポートを正しく分類する

### Requirement 3: CI/CDパイプライン更新

**Objective:** CI/CD管理者として、CIパイプラインでruff formatを使用したい。これにより、black/isortチェックをruff単体に統合できる。

#### Acceptance Criteria 3

1. The CI pipeline shall `.github/workflows/ci.yml`で`ruff format --check .`を実行する
2. The CI pipeline shall フォーマット違反時にビルドを失敗させる
3. The CI pipeline shall `ruff check`と`ruff format --check`を順次実行する
4. When フォーマットチェックが失敗した場合, the CI pipeline shall 違反ファイルのパスを出力する

### Requirement 4: 開発ワークフロー更新

**Objective:** 開発者として、更新されたフォーマットコマンドを使用したい。これにより、日常の開発作業でruffを活用できる。

#### Acceptance Criteria 4

1. The development workflow shall `ruff format .`コマンドでフォーマットを実行できる
2. The development workflow shall `ruff check --fix .`コマンドでリント修正とインポートソートを実行できる
3. The VSCode tasks shall 「Ruff Check」タスクで`ruff check`と`ruff format --check`の両方を実行する
4. The VSCode tasks shall 「Ruff Fix」タスクで`ruff check --fix`と`ruff format`の両方を実行する
5. The pre-commit hook shall ruff formatを使用してフォーマットチェックを行う（pre-commit設定が存在する場合）

### Requirement 5: ドキュメント更新

**Objective:** 開発者として、更新されたフォーマット手順をドキュメントで確認したい。これにより、新規参加者も正しいツールを使用できる。

#### Acceptance Criteria 5

1. The steering documentation shall `tech.md`のCode Quality/Formatterセクションをruffに更新する
2. The steering documentation shall Common Commandsセクションを`ruff format .`に更新する
3. If READMEにフォーマットコマンドが記載されている場合, the documentation shall 該当箇所をruffコマンドに更新する

### Requirement 6: 依存関係整理

**Objective:** 開発者として、不要になったフォーマッター依存を削除したい。これにより、依存関係がシンプルになる。

#### Acceptance Criteria 6

1. The dependency configuration shall blackをrequirements（dev）から削除する
2. The dependency configuration shall isortをrequirements（dev）から削除する（ruffで代替する場合）
3. The dependency configuration shall ruffの必要バージョンを明示する
4. If pyproject.tomlに`[tool.black]`セクションが存在する場合, the configuration shall 該当セクションを削除する
5. If pyproject.tomlに`[tool.isort]`セクションが存在する場合, the configuration shall 該当セクションを削除または`[tool.ruff.lint.isort]`に移行する
