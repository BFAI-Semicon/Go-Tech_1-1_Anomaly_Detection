# 2026年度 研究計画

## 全体方針

前半は既存手法の深化、後半は自己教師あり学習（DINO / DINOv2 / MAE 等で事前学習した ViT を重み固定で活用）による欠陥検出手法調査を行う。

- データ：前半MIIC, 後半独自データ
- 評価：AUROC / AUPRC / F1 /（領域）IoU・PRO

---

## 前半：既存手法 × 前後処理 × アンサンブル

2025年度調査（`Survey/research_plan.md`）の延長として、MIIC 上で
教師なし異常検知の上限性能を特定する。

### 対象手法

- PaDiM / PatchCore / FastFlow / CFlow / DFM / DFKDE
- EfficientAD / DRAEM / AnomalyDINO / WinCLIP

### 前処理

- コントラスト補正（CLAHE / Retinex）
- ノイズ除去（BM3D / NLM / Bilateral）
- タイル化（サイズ・重複率）
- 正規化（per-image / percentile clip）

### 後処理

- ヒートマップ平滑化（Gaussian / Guided Filter）
- 形態学処理（open/close / top-hat）
- 閾値決定（Otsu / percentile / validation-based）
- 連結成分フィルタ（サイズ・縦横比）

### アンサンブル

- 異種手法の score-level fusion（PatchCore × FastFlow × DRAEM 等）
- 平均 / 重み付き平均 / rank fusion / 学習型ゲート
- 各手法の得意欠陥タイプを混同行列で分解

### 前半アウトプット

- MIIC 上の非学習ベースライン上限
- 採用特徴抽出器・前後処理・融合方式の固定
- 残存する誤検出・見逃しの類型化（後半 HITL 入力）

---

## 後半：自己教師あり学習による Promptable Patch Retrieval

`researches.md` に基づく、自己教師あり学習で獲得した ViT 表現を**重み固定のまま（推論時適応）** 用いる工程横断欠陥検出。

### 構成要素

- **固定 ViT 特徴抽出**：重み更新なし、パッチ特徴量の大量生成
- **特徴量ストア**：FAISS 等による kNN 近傍検索基盤
- **一次検出**：前半で選定したベース（例：PatchCore on DINOv2）
- **人間フィードバック**：ROI 丸付け ＋ 自然言語コメント
- **LLM 構造化**：コメント → JSON（scope / judgment / priority / expiry）
- **補正レイヤ**：スコア再重み付け / 閾値適応 / ラベル上書き

### 評価軸

- ROI のみ vs 言語のみ vs 併用
- スコア補正 vs ラベル上書き
- 工程内汎化 vs 工程横断汎化（Si ↔ 化合物）
- フィードバック1件あたりの改善量

### 計算資源検証

- DGX Spark 実測：パッチ数 × スケール × ストア規模のスイープ
- PC GPU との比較で要件根拠を定量化

---

## 前半 → 後半のブリッジ

| 前半成果 | 後半での再利用 |
| --- | --- |
| 前処理ベストプラクティス | 推論パイプライン先頭に共通化 |
| 特徴抽出器評価 | 固定 ViT 選定根拠 |
| 誤検出・見逃し類型 | HITL 評価シナリオ |
| score fusion 実装 | 一次検出 + 補正レイヤの fusion |
| 評価スクリプト | LOPO・HITL 評価に流用 |

---

## リスクと対策

- **MIIC 異常 116 枚の統計不安定**：stratified k-fold + bootstrap CI
- **DINOv2 等のライセンス**：早期に法務確認
- **LLM JSON 化の逸脱**：構造化出力 + スキーマ検証、失敗時の監査ログ
- **DGX Spark 到着遅延**：PC GPU で走る縮約設定を事前用意
