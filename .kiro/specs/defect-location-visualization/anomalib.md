# anomalibにおける可視化機能調査

## 1. 可視化アウトプットの種類

Anomalib の推論・評価パイプラインでは、主に以下の可視化成果物が出力されます。

### 1.1. Anomaly Heatmap

* 各ピクセルの異常スコアを連続値で表現
* 赤（高異常）〜青（正常）などのカラーマップ

### 1.2. Segmentation Mask

* 閾値処理後の2値マスク
* NG領域の面積算出・重心算出などに利用可

### 1.3. Overlay Image

* 元画像 + ヒートマップ重畳
* 現場説明・レポート用途で最も実用的

### 1.4. Bounding Box（モデル依存）

* ヒートマップから外接矩形抽出
* 外観検査UI向け

---

## 2. 出力例イメージ

（典型的な industrial AD 可視化）

### Heatmap / Overlay / Mask

![Image](https://docs.voxel51.com/_images/anomaly_detection_thumbnail.jpg)

![Image](https://dataroots.io/api/social-preview?backgroundImgUrl=https%3A%2F%2Fdataroots.ghost.io%2Fcontent%2Fimages%2F2023%2F01%2Fpatchcore_results.png\&description=Anomaly+detection+in+images+using+PatchCore\&height=630\&previewImgUrl=\&subdescription=by+Toon+Van+Craenendonck\&title=\&width=1200)

![Image](https://qiita-user-contents.imgix.net/https%3A%2F%2Fqiita-image-store.s3.ap-northeast-1.amazonaws.com%2F0%2F264921%2Fe7651217-ce33-4a25-9503-8990940c845b.png?auto=format\&gif-q=60\&ixlib=rb-4.0.0\&q=75\&s=a088b12698a3dff56ec6d497f7f1194b)

![Image](https://miro.medium.com/v2/resize%3Afit%3A1400/1%2AODgUltRyfYJg6QJzYX0s8Q.png)

※実際の anomalib 出力もほぼこの形式になります。

---

## 3. モデル系統別の可視化特性

ユーザー提示の10モデルを、可視化観点で整理します。

|     系統     |      モデル例      | 解像度 |          特徴          |
| ------------ | ------------------ | ------ | ---------------------- |
| Feature      | PaDiM / PatchCore  | 中〜高 | 特徴距離ベース heatmap |
| Flow         | FastFlow / CFlow   | 高     | 密度分布の歪みを可視化 |
| KDE / 統計   | DFKDE / DFM        | 中     | 異常確率分布           |
| Reconstruct  | DRAEM              | 非常高 | 再構成誤差を直接可視化 |
| VLM / Trans. | WinCLIP / AnomDINO | 中     | Attention / 差分       |

---

## 4. 実際の出力ディレクトリ構造

典型的な `anomalib predict` / `test` 実行後：

```text
results/
 └── <model>/
      └── <dataset>/
           ├── images/
           │    ├── 000_overlay.png
           │    ├── 000_heatmap.png
           │    └── 000_mask.png
           │
           ├── pixel_predictions.csv
           └── image_predictions.csv
```

---

## 5. CLI 実行時の有効化

可視化は **デフォルト有効** ですが、明示指定も可能。

```bash
anomalib predict \
  --model padim \
  --dataset mvtec \
  --visualization true
```

もしくは config:

```yaml
visualization:
  save_images: true
  log_images: true
```

---

## 6. Python API での取得

```python
from anomalib.deploy import Predictor

predictor = Predictor(
    model_path="weights/model.ckpt",
    device="cuda"
)

result = predictor.predict("test.png")

heatmap = result.heat_map
mask = result.pred_mask
overlay = result.segmentations
```

---

## 7. 評価時の可視化（Test / Validation）

学習後の `test` フェーズでも自動生成されます。

用途：

* AUROC の定性確認
* False Positive 分析
* ドメインシフト検出
* ラベル誤り検知

---

## 8. 産業用途での実務的使い分け

あなたの半導体検査ユースケース前提で整理：

|    可視化     |          用途          |
| ------------- | ---------------------- |
| Heatmap       | 欠陥強度評価           |
| Mask          | 面積・個数算出         |
| Overlay       | 現場説明               |
| Pixel CSV     | SPC / トレーサビリティ |
| Video Overlay | ライン検査             |

---

## 9. 注意点（重要）

### 9.1. Feature-based は輪郭がぼやける

* PatchCore / PaDiM は特徴空間距離
* ピクセル境界は粗い

### 9.2. Reconstruction は輪郭が鋭い

* DRAEM / AE 系
* 微細クラックに強い

### 9.3. Flow は中間

* 分布異常を滑らかに検出

---

## 10. まとめ

* Anomalib は **異常可視化を標準搭載**
* 出力形式：
  * Heatmap
  * Mask
  * Overlay
  * CSV
* 全モデル系統で利用可
* Localization 評価（PRO, Pixel-AUROC）にも直結
