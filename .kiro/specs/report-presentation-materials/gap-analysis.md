# ギャップ分析レポート: report-presentation-materials

## 分析サマリー

- **成果物**: Marp 互換 Markdown ファイル 1 式（Python 等のコード成果物なし）
- **既存 Marp 資産**: リポジトリ内に Marp ファイルは **0 件**。
  新規作成が必要
- **ソースコンテンツ**: `docs/` 配下に文献調査・モデル検証・
  論文詳細分析が揃っており、スライドに転記可能な情報量は十分
- **ツール環境**: Marp for VS Code 拡張は devcontainer に導入済み。
  `marp-cli` は未インストール（PDF/HTML 出力には追加導入が必要）
- **主なギャップ**: Marp テンプレート不在、
  非専門家向け平易表現の執筆、スライド枚数制限内への情報圧縮

## 1. 現状調査

### 1.1 既存アセット

|カテゴリ|状態|備考|
|---|---|---|
|Marp ファイル|なし|`marp: true` を含むファイルなし|
|Marp for VS Code|導入済み|devcontainer に拡張設定あり|
|marp-cli|未導入|PDF/HTML 変換には別途導入が必要|
|プレゼンテンプレート|なし|スライドテーマ・CSS なし|

### 1.2 利用可能なソースコンテンツ

|要件|ソースファイル|情報量|
|---|---|---|
|Req2-AC1: 文献調査|`survey_results.md`|303 行|
|Req2-AC2: 論文サーベイ|`4papers_for_semicon_industry.md`|57 行|
|Req2-AC2: Barusco 論文|`Barusco_etal_2025.md`|148 行|
|Req2-AC3: モデル検証|`MIIC_10models.md`|70 行|
|Req2-AC4: LeadersBoard|`product.md`（steering）|ステータス情報|
|Req3: 【１－２】|`docs/index.md`|実施中のみ|
|補足: 調査計画|`research_plan.md`|90 行|

### 1.3 コンテンツの充実度

- **【１－１】教師なし学習**: 文献調査 + Barusco 論文の性能比較表 +
  10 モデル検証計画 + LeadersBoard 成果と、
  スライド 6〜8 枚分の情報が十分に存在する
- **【１－２】欠陥箇所の可視化**: `docs/index.md` に
  「現在実施中」とあるのみで、具体的な活動内容・方針の記載がない。
  **1 スライド程度の記載が上限**

## 2. 要件実現可能性分析

### 2.1 要件 → アセットマッピング

|要件|AC|対応アセット|ギャップ|
|---|---|---|---|
|Req1|AC1-4|固定情報（タイトル・所属・氏名）+ `docs/index.md` 構成|なし（情報は揃っている）|
|Req2|AC1|`survey_results.md`|要約・圧縮が必要（303 行 → 1-2 スライド）|
|Req2|AC2|`4papers_for_semicon_industry.md` + `Barusco_etal_2025.md`|要約・圧縮が必要。比較表はそのまま転用可|
|Req2|AC3|`MIIC_10models.md`|モデル一覧テーブルは転用可|
|Req2|AC4|`product.md`|ステータス情報は揃っている|
|Req3|AC1-2|`docs/index.md`|**具体的な活動内容・方針が不足**。「実施中」のみ|
|Req4|AC1-5|—|構成・ストーリーラインの設計が必要（新規作成）|
|Req5|AC1-4|—|Marp ディレクティブ・テーマの選定が必要|
|Req6|AC1-4|Marp for VS Code 導入済み|marp-cli 未導入（Missing）|

### 2.2 ギャップ一覧

|ID|種別|内容|影響度|
|---|---|---|---|
|G1|Missing|Marp ファイルが存在しない（新規作成）|低（想定内）|
|G2|Missing|marp-cli 未導入（PDF/HTML 出力不可）|中（プレビューは VS Code で可能）|
|G3|Missing|Marp テーマ/CSS カスタム未設定|低（built-in テーマで開始可能）|
|G4|Constraint|303 行の文献調査を 1-2 スライドに圧縮|中（情報設計が必要）|
|G5|Constraint|【１－２】の具体情報が不足|低（「実施中」の 1 スライドで対応可能）|
|G6|Constraint|非専門家向け平易表現の執筆|中（導入・結論で技術用語の言い換えが必要）|
|G7|Research Needed|Marp での Mermaid 図サポート範囲の確認|低（テキスト・テーブルで代替可能）|

## 3. 実装アプローチ

### Option A: 単一 Markdown ファイルで完結（推奨）

**根拠**: 成果物が Marp Markdown 1 ファイルであり、
外部依存を最小化する要件と整合する。

- `docs/` 直下に `report.md` を作成
- Marp フロントマターで built-in テーマ（default/gaia/uncover）を指定
- 全スライドを 1 ファイルに収録
- 発表者ノートをコメントで埋め込み

**トレードオフ**:

- 利点: シンプル、Marp for VS Code で即プレビュー可、
  外部依存ゼロ
- 欠点: カスタムテーマによるブランディングなし

### Option B: カスタムテーマ CSS + Markdown ファイル

**根拠**: 所属組織のブランディングを反映したい場合。

- `docs/` に `report.md` + `theme/bfai.css` を作成
- Marp カスタムテーマで組織カラー・フォントを設定
- フロントマターで `theme: bfai` を指定

**トレードオフ**:

- 利点: プロフェッショナルな見た目、ブランド統一
- 欠点: CSS 作成の追加工数、
  Marp for VS Code でカスタムテーマ設定が必要

### Option C: Marp + marp-cli パイプライン

**根拠**: CI/CD で PDF 自動生成まで行いたい場合。

- Option A or B + `package.json` に marp-cli スクリプト追加
- `npm run build:slides` で PDF/HTML 出力

**トレードオフ**:

- 利点: 再現可能なビルド、CI 統合可能
- 欠点: Node.js / npm 依存の追加、
  本フィーチャーのスコープを超える可能性

## 4. 工数・リスク評価

### 工数: **S（1〜3 日）**

- Markdown 1 ファイルの新規作成
- 既存 docs からの情報転記・要約
- Marp ディレクティブ設定
- 非専門家向け表現の推敲

### リスク: **低**

- 既存コードベースへの変更なし（新規ファイル追加のみ）
- ソースコンテンツは十分に存在
- Marp for VS Code は導入済みでプレビュー可能
- 技術的に未知の要素なし

## 5. 設計フェーズへの推奨事項

### 推奨アプローチ: Option A（単一ファイル）

- 最もシンプルで要件に合致
- marp-cli は設計フェーズで必要に応じて検討

### 設計フェーズで決定すべき事項

1. **スライド構成の詳細設計**: 各スライドのタイトル・
   コンテンツ概要・枚数配分
1. **Marp テーマ選定**: default / gaia / uncover のいずれか
1. **情報圧縮方針**: 文献調査 303 行 →
   1-2 スライドへの要約ルール
1. **非専門家向け表現**: 導入・結論スライドの
   具体的な言い回し・用語置換リスト

### Research Needed（設計フェーズで調査）

- Marp built-in テーマの見た目比較と選定
- 発表者ノートの出力形式（PDF ノート付き出力の可否）
