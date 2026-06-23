# 2026年度 研究計画

## 全体方針

前半は PatchCore の蒸留による軽量化を主軸に既存手法を深化させ、後半は
自己教師あり学習（DINO / DINOv2 / MAE 等で事前学習した ViT を重み固定で活用）
による欠陥検出手法調査を行う。

- データ：前半MIIC, 後半独自データ
- 評価：AUROC / AUPRC / F1 /（領域）IoU・PRO

---

## 前半：PatchCore 蒸留 ＋ 既存手法ベース整備

中間報告（`docs/NITech_report.md`）の結論「PatchCore をベースにメモリ使用量を
削減し推論速度を向上させる」を受け、PatchCore の蒸留検証を前半の主軸に据える。

### PatchCore 蒸留検証（主軸）

精度を維持したまま、PatchCore のメモリ使用量（メモリバンク）と
推論速度のトレードオフを改善する。

- **教師**：MIIC で構築した PatchCore（メモリバンク ＋ kNN 異常スコア）
- **生徒**：軽量 CNN / 小型バックボーン（メモリバンク不要の forward 推論）
- **蒸留方式**：特徴蒸留（教師の patch 埋め込み回帰）／
  異常マップ蒸留（教師の異常スコアマップ再現）
- **検証軸**：coreset 率[^coreset]と精度の関係、生徒の FPS・GPU メモリ・精度の
  トレードオフ、欠陥サイズ別（小/中/大）の精度劣化（中間報告 評価②に対応）
- **目標**：AUROC を維持しつつ FPS 向上・GPU メモリ削減
- **評価指標**：AUROC / AUPRC / F1 ＋ FPS・GPU メモリ

[^coreset]: coreset 率：PatchCore のメモリバンクに残す代表特徴の割合
    （選択特徴数 / 全特徴数）。低いほどメモリ↓・速度↑だが精度低下のリスク↑。

### 既存手法 × 前後処理 × アンサンブル（補完）

蒸留の教師・比較対象として、MIIC 上の教師なし異常検知の上限性能を簡潔に押さえる。

- **対象手法**：PaDiM / PatchCore / FastFlow / CFlow / DFM / DFKDE ＋
  EfficientAD / DRAEM / AnomalyDINO / WinCLIP
- **前処理**：CLAHE/Retinex、BM3D/NLM/Bilateral、タイル化、正規化
- **後処理**：ヒートマップ平滑化、形態学処理、閾値決定、連結成分フィルタ
- **アンサンブル**：異種手法の score-level fusion（平均/重み付き/rank/学習型ゲート）

### 前半アウトプット

- PatchCore 蒸留モデル（軽量・高速版）と精度/速度/メモリのトレードオフ表
- MIIC 上の教師なし異常検知のベースライン上限と採用構成（特徴抽出器・前後処理・融合）の固定
- 残存する誤検出・見逃しの類型化（後半 Human in the loop (HITL) 入力）

---

## 後半：自己教師あり学習による Promptable Patch Retrieval

`researches.md` に基づく、自己教師あり学習（DINO 系の自己蒸留／MAE のマスク再構成）で
獲得した ViT 表現を**重み固定のまま（推論時適応）** 用いる工程横断欠陥検出。

### 構成要素

- **Self-Supervised Learning (SSL) 事前学習 ViT（重み固定）**：DINOv2 系の埋め込みと MAE 再構成誤差をパッチ単位で生成
- **特徴量ストア**：FAISS 等による kNN 近傍検索基盤（工程・材料・装置タグでメタ分割）
- **一次検出**：埋め込み逸脱（PatchCore on DINOv2 等）と MAE 再構成誤差の融合
- **人間フィードバック**：ROI 丸付け ＋ 自然言語コメント
- **LLM 構造化**：コメント → JSON（scope / judgment / priority / expiry）
- **補正レイヤ**：スコア再重み付け / 閾値適応 / ラベル上書き

### 評価軸

- ROI のみ vs 言語のみ vs 併用
- スコア補正 vs ラベル上書き
- 工程内汎化 vs 工程横断汎化（Si ↔ 化合物）
- フィードバック 1 件あたりの改善量
- **SSL 特徴抽出器比較**：ImageNet 教師あり CNN vs DINO / DINOv2 vs DINO + MAE vs C-RADIOv2

### 計算資源検証

- DGX Spark 実測：パッチ数 × スケール × ストア規模のスイープ
- PC GPU との比較で要件根拠を定量化

---

## 前半 → 後半のブリッジ

| 前半成果 | 後半での再利用 |
| --- | --- |
| 前処理ベストプラクティス | 推論パイプライン先頭に共通化 |
| 特徴抽出器評価 | SSL 事前学習 ViT 選定根拠 |
| 誤検出・見逃し類型 | HITL 評価シナリオ |
| score fusion 実装 | 一次検出 + 補正レイヤの fusion |
| 評価スクリプト | LOPO・HITL 評価に流用 |

---

## リスクと対策

- **MIIC 異常 116 枚の統計不安定**：正常分割の k-fold（全異常をテストで使用）
  ＋ bootstrap 信頼区間 (Confidence Interval, CI)
- **DINOv2 等のライセンス**：早期に法務確認
- **LLM JSON 化の逸脱**：構造化出力 + スキーマ検証、失敗時の監査ログ
- **事前学習ドメインギャップ**：MAE のドメイン適応／産業横断モデル（C-RADIOv2 等）を検討
- **撮像条件変動が欠陥より支配的**：scope 単位の分布推定・複数プロトタイプによる代表づけ
- **DGX Spark 到着遅延**：PC GPU で走る縮約設定を事前用意
