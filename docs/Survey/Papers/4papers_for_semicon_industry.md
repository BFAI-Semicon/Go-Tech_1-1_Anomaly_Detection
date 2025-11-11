# 4 papers for semiconductor industry

---

## **1) Huang, S. H. & Pan, Y. C. (2015)**

- **タイトル：** Automated Visual Inspection in the Semiconductor Industry: A Survey
- **掲載誌：** *Computers in Industry, 66*, 1–10
- **分類：** 学術論文（ジャーナル）

- **要約：**
この論文は、半導体製造における自動外観検査（Automated Visual Inspection, AVI）の技術動向を体系的に整理した初期の総説です。画像処理・パターン認識・機械学習を利用した欠陥検出手法を中心に、ウェーハ検査、パッケージ検査、マスク検査などの応用領域を網羅しています。主な課題として、微細化に伴う欠陥の多様化、照明条件のばらつき、リアルタイム処理の制約などを挙げ、今後は「知的検査」への進化が必要と指摘しています。

---

## **2) Hütten, N. et al. (2024)**

- **タイトル：** Deep Learning for Automated Visual Inspection in Manufacturing and Maintenance: A Survey of Open-Access Papers
- **掲載誌：** *Applied System Innovation*, 7(1):11
- **分類：** 学術論文（オープンアクセス・ジャーナル）

- **要約：**
この論文は、製造業および保全分野におけるディープラーニングを用いた自動外観検査の最新動向を網羅的に調査したサーベイです。特にオープンアクセス文献を中心に収集し、CNN、GAN、Transformersなどの主要アーキテクチャ別に分類・分析しています。学術研究の多くは特定データセット上で高精度を示すものの、実運用での一般化・ドメイン適応・データアノテーション負荷などが未解決課題であると指摘しています。

---

## **3) Schlosser, T. et al. (2022)**

- **タイトル：** Improving Automated Visual Fault Inspection for Semiconductor Manufacturing Using a Hybrid Multistage System of Deep Neural Networks
- **掲載誌：** *Journal of Intelligent Manufacturing*, 33, 1099–1123
- **分類：** 学術論文（ジャーナル）

- **要約：**
本研究では、半導体製造の欠陥検査精度を向上させるため、複数のディープニューラルネットワークを段階的に組み合わせたハイブリッド検査システムを提案しています。初期段階では粗い欠陥候補を検出し、後段で分類精度を高める多段アプローチにより、誤検出率を大幅に低減しています。実験結果では、従来の単一ネットワーク構成に比べてF1スコアや再現率が有意に向上し、実ラインへの適用可能性が示されています。

---

## **4) Barusco, M. et al. (2025)**

- **タイトル：** Evaluating Modern Visual Anomaly Detection Approaches in Semiconductor Manufacturing: A Comparative Study
- **掲載誌：** *arXiv preprint, arXiv:2505.07576*
- **分類：** プレプリント論文（arXiv, 未査読）

- **要約：**
この最新研究は、半導体製造における異常検知（Anomaly Detection）手法の比較評価を目的としています。PaDiM、PatchCore、CFA、DRAEM、SAAなどの代表的ディープラーニング手法を共通データセット上で比較し、精度、推論速度、計算資源消費を総合的に分析しました。結果として、PatchCore系が高精度かつ高速で実用的である一方、SAAなど生成モデル系は微小欠陥の再現性に優れることが示されています。産業応用における評価ベンチマークの重要性も強調されています。詳細は[こちら](./Barusco_etal_2025.md)。

---

## ✅ まとめ表

| No  | 著者（年）              | タイトル（略）                                        | 出典                                   | 分類                 | 主題                        |
| --- | ----------------------- | ----------------------------------------------------- | -------------------------------------- | -------------------- | --------------------------- |
| 1   | Huang & Pan (2015)      | Automated Visual Inspection in Semiconductor Industry | *Computers in Industry*                | ジャーナル論文       | 半導体AVI技術の初期サーベイ |
| 2   | Hütten et al. (2024)    | Deep Learning for Automated Visual Inspection         | *Applied System Innovation*            | オープンアクセス論文 | 製造業向け深層学習AVIの総説 |
| 3   | Schlosser et al. (2022) | Hybrid Multistage DNN System                          | *Journal of Intelligent Manufacturing* | ジャーナル論文       | 多段DNNによる検査精度向上   |
| 4   | Barusco et al. (2025)   | Comparative Study of Anomaly Detection                | *arXiv preprint*                       | プレプリント論文     | 異常検知モデルの比較評価    |
