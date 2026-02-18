---
marp: true
theme: default
paginate: true
header: "AI画像検査技術の研究開発"
footer: "株式会社BFAIセミコンダクタソリューションズ"
---

<!-- _paginate: skip -->
<!-- _header: "" -->
<!-- _footer: "" -->

# 高度判断能力と応用拡張性を持つ先端半導体製造ライン向けＡＩ画像検査技術の研究開発

所属: **株式会社BFAIセミコンダクタソリューションズ**

報告者: 長島剛宏
報告日: 2026-02-19

<!--
表紙スライド。
管理機関および経済産業省中部経済産業局の担当者向け報告資料。
-->

---

## 目次

1. 研究開発の背景と目的
2. 実施内容
   1. 【１－１】教師なし学習に基づく異常判定機能の設計
      1. 文献調査
      2. モデル検証計画
      3. モデル検証環境
   2. 【１－２】欠陥箇所の可視化機能の設計
3. まとめと今後の計画

<!--
docs/index.md の構成に対応した目次です。
【１－１】は文献調査・実験の成果を報告し、
【１－２】は現在実施中であることをお伝えします。
-->

---

## 1. 研究開発の背景と目的

### 背景

半導体の品質検査は現在、人の目に頼る部分が多く、検査の速度と精度に限界

### 研究の目的

- AI画像検査技術により人間を上回る高精度化
- 製品仕様やデザイン変更などに対応し得る汎用化

<!--
「教師なし学習」とは、正常な画像だけを手本にして学ぶ AI のことです。
「異常検知」とは、不良品を自動で見つける技術です。
「SEM 画像」とは、電子顕微鏡で撮影した半導体の拡大画像です。
-->

---

## 2. 実施内容

### i. 【１－１】教師なし学習に基づく異常判定機能の設計

---

#### a. 文献調査（1/3）— 手法調査

##### WE-PaDiM (Gardner et al., 2025)

- PaDiM に離散ウェーブレット変換（DWT）を統合した改良版
- MVTec AD で Image-AUC 99.32%、Pixel-AUC 92.10%
- 産業用異常検知に特化、PaDiM と同等の推論効率
- 課題: ライセンスファイル未提供、商用利用不可（推定）

##### PaDiM-ACE (Ibarra & Peeples, 2025)

- PaDiM に Adaptive Cosine Estimator を導入した改良版
- 合成開口レーダー（SAR）画像向けに特化、有界異常検知スコアの提供
- 課題: 半導体製造とは異なるドメイン、性能スコア未記載

<!--
出典: docs/Survey/Papers/survey_results.md
-->

---

#### a. 文献調査（2/3）— 半導体製造向け論文

##### Huang & Pan (2015)

- 半導体製造における自動外観検査（AVI）技術の初期総説
- ウェーハ・パッケージ・マスク検査などの応用領域を網羅
- 課題: 微細化に伴う欠陥の多様化、照明条件のばらつき、リアルタイム処理の制約

##### Hütten et al. (2024)

- 製造業・保全分野における深層学習 AVI の最新サーベイ
- CNN・GAN・Transformers 等の主要アーキテクチャ別に分類・分析
- 課題: 実運用での一般化・ドメイン適応・データアノテーション負荷

<!--
出典: docs/Survey/Papers/4papers_for_semicon_industry.md
-->

---

#### a. 文献調査（3/3）— 半導体製造向け論文

##### Schlosser et al. (2022)

- 多段 DNN によるハイブリッド検査システムの提案
- F1 スコア・再現率が単一ネットワーク構成より有意に向上
- 実製造ラインへの適用可能性を実証

##### Barusco et al. (2025)

- PaDiM・PatchCore・CFA・DRAEM 等の比較評価
- PatchCore 系が高精度かつ高速で実用的
- 産業応用における評価ベンチマークの重要性を強調

<!--
出典: docs/Survey/Papers/4papers_for_semicon_industry.md
-->

---

#### b. モデル検証計画

##### MIIC データセット概要

- [MIIC（Manufacturing Industrial Inspection Challenge）](https://researchdata.ntu.edu.sg/dataset.xhtml?persistentId=doi:10.21979/N9/WBLTFI)
- 製造業向け外観検査AIの性能評価を目的としたベンチマークデータセット
- 半導体 IC の電子顕微鏡（SEM）グレースケール画像
- 実製造ラインに近い撮像条件を反映
- **正常画像**: 25,160 枚 / **異常画像**: 116 枚

##### 検証対象モデル

- モデルは付録 A-1 参照

**評価指標**: AUROC, AUPRC, F1-Score

<!--
出典: docs/Survey/Experiments/MIIC_10models.md
AUROC = 検知精度を測る指標
AUPRC = 不均衡データでの精度指標
全 10 モデルの詳細は付録 A2 を参照してください。
-->

---

#### c. モデル検証環境

AI モデルの性能を評価・比較する環境

##### 概要

コード提出 → GPU 学習・評価 → 結果可視化の自動パイプライン

##### 主要機能

- コード受付、非同期ジョブ実行、計算結果管理

<!--
出典: .kiro/steering/product.md
技術詳細: Clean-lite 設計（依存逆転）、ポート/アダプタパターン、
FastAPI + Redis + MLflow + Streamlit のコンテナ構成。
口頭で補足します。
-->

---

#### ii. 【１－２】欠陥箇所の可視化機能 — 現在設計中

異常検知モデルの出力を活用した以下の可視化手法を予定

- **Anomaly Heatmap** — 各ピクセルの異常スコアのカラーマップ表現
- **Segmentation Mask** — 閾値処理後の 2 値マスクによる
  NG 領域の面積・重心算出
- **Overlay Image** — 元画像へのヒートマップ重畳、
  現場説明・レポート用途
- **Bounding Box** — ヒートマップからの外接矩形抽出、
  外観検査 UI 向け

<!--
出典: docs/index.md
可視化手法の 4 分類（Heatmap / Mask / Overlay / BBox）を
設計・検証予定。詳細は今後の報告でお伝えします。
-->

---

## まとめと今後の計画

### これまでの成果

- 最新の AI 画像検査技術を調査
- 半導体検査に有望な手法を選定
- 半導体画像での検証計画を策定
- 手法の性能を客観的に比較する計算基盤構築

### 今後の計画

- 選定した手法の半導体画像での検証
- 手法、モデルの改良
- 異常箇所の可視化
- 実製造ラインへの適用に向けた課題整理

<!--
成果対応: 文献調査→S5, モデル比較→S6, 検証計画→S7, LeadersBoard→S8
課題と計画は非専門家でも理解できる表現にしています。
-->

---

<!-- _header: "付録" -->

## 付録 A-1: 検証対象 10 モデル一覧（1/2）

<!-- markdownlint-disable MD013 -->

| No | Model     | 系統           | 異常検知原理  | 主用途           |
| -- | --------- | -------------- | ------------- | ---------------- |
| 1  | PaDiM     | 統計・埋め込み | Feature-based | ベースライン     |
| 2  | PatchCore | メモリバンク   | Feature-based | 高精度本命       |
| 3  | FastFlow  | Flow           | Feature-based | 高速推論         |
| 4  | CFlow     | Flow           | Feature-based | 分布ばらつき対応 |
| 5  | DFM       | 統計           | Feature-based | 安定性           |

<!-- markdownlint-enable MD013 -->

<!--
出典: docs/Survey/Experiments/MIIC_10models.md
評価指標: AUROC, AUPRC, F1-Score
-->

---

<!-- _header: "付録" -->

## 付録 A-2: 検証対象 10 モデル一覧（2/2）

<!-- markdownlint-disable MD013 -->

| No | Model       | 系統        | 異常検知原理         | 主用途       |
| -- | ----------- | ----------- | -------------------- | ------------ |
| 6  | DFKDE       | KDE         | Feature-based        | ドリフト検知 |
| 7  | EfficientAD | 工業向け    | Feature-based        | Edge 展開    |
| 8  | DRAEM       | 再構成      | Reconstruction-based | 説明性       |
| 9  | AnomalyDINO | Transformer | Feature-based        | 次世代       |
| 10 | WinCLIP     | VLM         | Feature-based        | 将来性評価   |

<!-- markdownlint-enable MD013 -->

<!--
出典: docs/Survey/Experiments/MIIC_10models.md
追加指標: 推論速度 (FPS), GPU メモリ消費量, 学習/推論時間
-->
