# 半導体画像に対するモデル検証

## データセット概要

### MIIC (Microscopic Images of Integrated Circuits)

集積回路（IC）の微細構造をスキャン電子顕微鏡（SEM）で撮影した画像を集めた異常検知データセット

#### データセット特性

- **正常画像**: 約25,160枚
- **異常画像**: 約116枚
- **画像タイプ**: 高解像度グレースケール SEM 画像
- **ドメイン**: 半導体製造・検査

#### 課題設定

- 正常データのみで学習し、異常を検知する教師なし異常検知
- 半導体画像特有の微細パターン認識が求められる
- 高解像度画像による計算コストの考慮が必要

## 検証対象モデル

| No  | Model       | 系統           | 異常検知原理             | 主用途           | ステータス |
| --- | ----------- | -------------- | ------------------------ | ---------------- | ---------- |
| 1   | PaDiM       | 統計・埋め込み | **Feature-based**        | ベースライン     | 未実施     |
| 2   | PatchCore   | メモリバンク   | **Feature-based**        | 高精度本命       | 未実施     |
| 3   | FastFlow    | Flow           | **Feature-based**        | 高速推論         | 未実施     |
| 4   | CFlow       | Flow           | **Feature-based**        | 分布ばらつき対応 | 未実施     |
| 5   | DFM         | 統計           | **Feature-based**        | 安定性           | 未実施     |
| 6   | DFKDE       | KDE            | **Feature-based**        | ドリフト検知     | 未実施     |
| 7   | EfficientAD | 工業向け       | **Feature-based**        | Edge展開         | 未実施     |
| 8   | DRAEM       | 再構成         | **Reconstruction-based** | 説明性           | 未実施     |
| 9   | AnomalyDINO | Transformer    | **Feature-based**        | 次世代           | 未実施     |
| 10  | WinCLIP     | VLM            | **Feature-based**        | 将来性評価       | 未実施     |

## 検証観点

- 精度検証
- 分布ばらつきやドリフトに対するロバストネス検証
- Transformer/VLM の有効性検証

## 評価指標

### 主要指標

- **AUROC**: Area Under Receiver Operating Characteristic
- **AUPRC**: Area Under Precision-Recall Curve
- **F1-Score**: PrecisionとRecallの調和平均

### 追加指標

- **推論速度**: FPS (Frames Per Second)
- **メモリ使用量**: GPUメモリ消費量
- **計算時間**: 学習/推論時間

## 課題と考察

### 技術的課題

- 高解像度画像によるメモリ制約
- SEM画像特有のノイズ・コントラスト特性
- 微細欠陥の検知精度

### 実用性考察

- 半導体検査プロセスへの適用可能性
- Edgeデバイスでの展開可能性
- 運用時の安定性とメンテナンス性
