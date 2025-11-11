# リーダーズボードデザインドック

## 目的

リーダーズボード用のOSS候補を洗い出すために、VAD向けフレームワークと一般的な実験管理/コンペ基盤を並行で調査。特に「anomalib」の対応手法とPROなどピクセル指標の有無、そして自前ホスティング可能なリーダーズボード基盤（EvalAI/CodaLab/OpenML、MLflow/Aim/ClearML）の適合性を確認。

## 要旨

- **最有力**: anomalib（VAD専用OSS）で評価を統一し、MLflow or Aim（OSSトラッカー）で「内製リーダーズボード」を構成。外部公開が必要なら EvalAI（OSSコンペ基盤）を併用。
- **理由**: anomalib は VAD 手法・指標（画像/ピクセル、含PRO）に強く、再現性の高い比較が可能。MLflow/Aim はメトリクスで並べ替え可能な表＝実質的なリーダーズボードを簡単に構築できる。EvalAI は公式公開用に適合。

## VAD専用フレームワーク（評価一式を任せられるOSS）

- **anomalib（OpenVINO/Intel）**  
  - **適合度**: 高。VADベンチマークの事実上の標準的OSS。MVTec/VisA/他の実装多数、学習/評価/可視化が一貫。画像・ピクセル指標（ROC-AUC、F1、PR、PRO など）に対応。  
  - **カバー手法の例**: PatchCore, PaDiM, FastFlow, STFPM, Reverse Distillation, DRAEM など（CFA/ SuperSimpleNet は未収載の可能性が高く、追加実装で拡張）。  
  - **メリット**: 同一コードで多手法を公平に比較、推論速度/メモリなども測りやすい。カスタムデータセット（MIIC）のアダプタも作りやすい。  
  - 参考: [anomalib GitHub](https://github.com/openvinotoolkit/anomalib), [Docs](https://anomalib.readthedocs.io)

## 自前ホストで「リーダーズボード」を作る（実験トラッキング系OSS）

- **MLflow**  
  - 実験追跡/比較に強い標準OSS。メトリクスで行をソートする「比較ビュー」がそのままリーダーズボードとして使える。REST/UI/DB 連携が容易。  
  - 参考: [MLflow](https://github.com/mlflow/mlflow)
- **Aim**  
  - 高速UIとクエリで、ランキング表を即席で構築。大量ランでも軽快。  
  - 参考: [Aim](https://github.com/aimhubio/aim)
- **ClearML（サーバOSS有）**  
  - ダッシュボードと比較表が使いやすい。オンプレで完結可能。  
  - 参考: [ClearML](https://github.com/allegroai/clearml)
- （補助）**TensorBoard（HParamsプラグイン）/ Sacred+Omniboard**  
  - 軽量に比較表を作る代替。要件がシンプルなら有効。  
  - 参考: [Sacred](https://github.com/IDSIA/sacred), [Omniboard](https://github.com/vivekratnavel/omniboard)

## 公開用のチャレンジ型リーダーズボード（自前ホスト可能なOSS）

- **EvalAI**  
  - 画像分類/セグメンテーション系の評価スクリプトを自作して登録すれば、PRO/ROC/F1 を公式LBに掲載可能。外部参加も受け付けられる。  
  - 参考: [EvalAI](https://github.com/Cloud-CV/EvalAI)
- **CodaLab（Codabench系）**  
  - 研究コミュニティで広く使われる自前ホスト型。評価ワーカーで任意指標を実装可。  
  - 参考: [Codabench](https://github.com/codalab/codabench)
- **OpenML**  
  - タスク/データ/フローを公開し、結果を共有・比較。VAD特化ではないが、標準化・公開性を重視する場合に候補。  
  - 参考: [OpenML](https://www.openml.org/)

## 推奨アーキテクチャ（最短で確実）

- **評価実行**: anomalib で PatchCore/PaDiM/FastFlow/STFPM/RD 等を統一条件で学習・評価（MIICはカスタムデータローダ追加）。  
- **記録とLB表示**: MLflow or Aim に下記メトリクスをログし、UIの「比較ビュー」をリーダーズボードとして運用。  
  - 画像レベル: ROC-AUC, F1, PR  
  - ピクセルレベル: ROC-AUC, F1, PR, PRO  
  - 付帯: 推論時間、VRAM、モデルサイズ など実運用指標  
- **外部公開が必要な場合**: EvalAI を自前で立ち上げ、評価スクリプトに PRO/ROC/F1 を実装してチャレンジを公開。

## 留意点（Barusco_etal_2025 との整合）

- MIICは「非商用（CC BY-NC 4.0）」のため、外部公開LB（EvalAI/OpenML）に流す前に利用条件を再確認。  
- anomalibに未収載の手法（CFA, SuperSimpleNet等）は、既存実装をラップして推論API/指標計算を合わせ込むと比較が容易。  
- ドメインギャップ（SEM特性）を踏まえ、特徴抽出器の微調整や評価の再現条件（解像度512×512、学習データ枚数等）を固定して比較することが重要。

ご希望であれば、anomalib + MLflow（または Aim）で「MIIC向け最小構成のリーダーズボード」雛形（評価スクリプト、メトリクス集計、表ビュー）をこちらで用意します。
