# arXiv検索手順ガイド

## 概要
半導体製造における異常検知手法の文献調査のため、arXiv Advanced Searchを使用した論文検索の手順をまとめます。

## arXiv Advanced Searchへのアクセス
- URL: https://arxiv.org/search/advanced

## 検索フィールドの説明

### 基本フィールド
- **Title**: 論文タイトル内を検索
- **Abstract**: アブストラクト内を検索
- **Author**: 著者名内を検索
- **Comments**: コメント内を検索

### 検索条件フィールド
- **Subject Class**: 分野を指定
- **Date Range**: 日付範囲を指定

## 複数条件検索の方法

### Add Fieldボタンの使用
1. 最初に表示されるフィールドに検索語を入力
2. 「Add Field」ボタンをクリック
3. 新しい検索フィールドが追加される
4. 複数の条件を組み合わせて検索可能

## 具体的な検索手順

### Step 1: 基本検索設定
```
Field 1:
- Title: [手法名] (例: PaDiM)

Subject Class: Computer Science (cs) にチェック
Date Range: 2023-01-01 から 2025-12-31
Submission date (most recent): 選択
```

### Step 2: 拡張検索（必要に応じて）
```
Field 1:
- Title: [手法名]

Field 2:
- Abstract: [関連キーワード] (例: "anomaly detection")

Subject Class: Computer Science (cs) にチェック
Date Range: 2023-01-01 から 2025-12-31
Submission date (most recent): 選択
```

### Step 3: 著者検索（必要に応じて）
```
Field 1:
- Author: [著者名] (例: "Xiaolin Li")

Subject Class: Computer Science (cs) にチェック
Date Range: 2023-01-01 から 2025-12-31
Submission date (most recent): 選択
```

## 対象手法別検索例

### PaDiM検索
```
Field 1:
- Title: PaDiM

Field 2:
- Abstract: "anomaly detection"

Subject Class: Computer Science (cs) にチェック
Date Range: 2020-2025 (基盤手法のため範囲拡大)
Submission date (most recent): 選択
```

### PatchCore検索
```
Field 1:
- Title: PatchCore

Field 2:
- Abstract: "anomaly detection"

Subject Class: Computer Science (cs) にチェック
Date Range: 2020-2025
Submission date (most recent): 選択
```

### SimpleNet検索
```
Field 1:
- Title: SimpleNet

Field 2:
- Abstract: "anomaly detection"

Subject Class: Computer Science (cs) にチェック
Date Range: 2022-2025
Submission date (most recent): 選択
```

## 日付範囲の設定指針

### 最新手法（2023-2025年）
```
From: 2023-01-01
To: 2025-12-31
理由: 最新の技術動向を把握
```

### 基盤手法（2020-2022年）
```
From: 2020-01-01
To: 2022-12-31
理由: 重要な基盤技術を調査
```

### 特定年（手法発表年）
```
例: PaDiMの場合
From: 2021-01-01
To: 2021-12-31
理由: 特定手法の発表年のみを調査
```

## 検索戦略

### 段階的検索アプローチ
1. **基本検索**: タイトルのみで検索
2. **拡張検索**: アブストラクトを追加
3. **著者検索**: 著者名を追加
4. **日付調整**: 結果に応じて日付範囲を調整

### 結果に応じた調整
- **結果が多い場合**:
  - 検索語を絞り込む
  - 日付範囲を狭める
  - より具体的なキーワードを使用

- **結果が少ない場合**:
  - 検索語を拡大
  - 日付範囲を拡大
  - 分野を拡大

## 検索結果の確認

### 確認すべき情報
- 論文タイトル
- 著者名
- 発表日
- arXiv ID
- アブストラクト（要約）

### PaDiM論文の特定例
```
探すべき情報:
- タイトル: "PaDiM: A Patch Distribution Modeling Framework for Anomaly Detection and Localization"
- 著者: Xiaolin Li, Yixiao Ge, Yixiao Liu, et al.
- 年: 2021
- arXiv ID: 2011.08785
```

## 検索結果の保存

### 論文のダウンロード
1. 論文タイトルをクリック
2. 「PDF」リンクをクリック
3. PDFをダウンロード
4. ファイル名を整理（例: PaDiM_2021.pdf）

### 情報の記録
Excel/Google Sheetsで以下の項目を記録:
- 論文ID
- タイトル
- 著者
- 年
- arXiv ID
- ダウンロード状況
- 優先度

## トラブルシューティング

### 検索結果が見つからない場合
1. スペルチェック
2. 検索語を変更
3. 日付範囲を拡大
4. 分野を変更
5. フィールドを削除

### 検索結果が多すぎる場合
1. 検索語を絞り込む
2. 日付範囲を狭める
3. 分野を限定
4. 追加フィールドを追加

## 効率的な検索のコツ

### 1. キーワードの準備
- 手法名（PaDiM, PatchCore等）
- 関連キーワード（anomaly detection, defect detection等）
- 著者名（第一著者名等）

### 2. 段階的な検索
- 最初は単一フィールドで検索
- 結果に応じて条件を追加・削除
- 複数の検索語を試す

### 3. 結果の管理
- 検索結果をExcelで管理
- 優先度を設定
- ダウンロード状況を記録

## 次のステップ

### 検索完了後の作業
1. PDFをダウンロード
2. アブストラクトを読む
3. 一次選別を実行
4. 優先度を設定
5. 次の手法を検索

### 文献管理ツールの活用
- Zotero等の文献管理ツールに保存
- タグ付け・分類
- ノート機能の活用

## 注意事項

### 著作権の遵守
- 論文の内容を適切に使用
- 引用形式の統一
- 参照元の記録

### 情報の更新
- 定期的な再検索
- 最新情報の確認
- リンク切れの対応

このガイドに従って、効率的で体系的な文献調査を実施してください。
