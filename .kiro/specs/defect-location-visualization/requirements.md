# Requirements Document

## Introduction

本ドキュメントは、LeadersBoardプラットフォームにおける「欠陥箇所の可視化機能」の要件を定義する。
anomalibによる異常検知モデルの評価結果として、ヒートマップ・セグメンテーションマスク・オーバーレイ画像などの可視化アーティファクトを生成・保存・表示し、研究者が欠陥箇所を視覚的に確認・比較できる機能を実現する。

### 背景

- anomalibは異常検知モデルの評価時に、Anomaly Heatmap / Segmentation Mask / Overlay Image を標準で出力可能
- 現状のWorkerは `metrics.json` の記録のみに対応しており、可視化アーティファクトの収集・保存・提供は未実装
- 半導体検査ユースケースでは、欠陥箇所の空間的な位置情報が品質管理・原因分析に不可欠

## Requirements

### Requirement 1: 可視化アーティファクト生成

**Objective:** 研究者として、anomalib評価実行時にヒートマップ・セグメンテーションマスク・オーバーレイ画像が自動生成されることで、モデルの欠陥検出結果を視覚的に確認したい

#### Acceptance Criteria

1. When Workerがanomalibモデルの評価を完了した時, the Worker shall 各テスト画像に対してAnomaly Heatmap（ピクセルレベルの異常スコアをカラーマップで表現した画像）を生成する
2. When Workerがanomalibモデルの評価を完了した時, the Worker shall 各テスト画像に対してSegmentation Mask（閾値処理後の2値マスク画像）を生成する
3. When Workerがanomalibモデルの評価を完了した時, the Worker shall 各テスト画像に対してOverlay Image（元画像にヒートマップを重畳した画像）を生成する
4. The Worker shall 生成する可視化画像をPNG形式で出力する
5. If anomalibの可視化処理中にエラーが発生した場合, the Worker shall エラー情報をログに記録し、メトリクス記録処理は継続する

### Requirement 2: 可視化アーティファクト保存

**Objective:** 研究者として、生成された可視化画像がアーティファクトとして永続化されることで、後から結果を参照・比較したい

#### Acceptance Criteria (Req 2)

1. When 可視化アーティファクトが生成された時, the Worker shall ヒートマップ・マスク・オーバーレイ画像をジョブのアーティファクトディレクトリ（`<artifact_root>/<job_id>/visualizations/`）に保存する
2. When 可視化アーティファクトがアーティファクトディレクトリに保存された時, the Worker shall TrackingPort経由でMLflowにアーティファクトとして記録する
3. The Worker shall 可視化アーティファクトのファイル名に元画像のファイル名と可視化種別（heatmap / mask / overlay）を含める
4. The Worker shall モデル系統に関わらず統一されたディレクトリ構造で可視化アーティファクトを出力する

### Requirement 3: 可視化結果の表示

**Objective:** 研究者として、Streamlit UIから可視化結果を閲覧できることで、欠陥箇所を視覚的に確認したい

#### Acceptance Criteria (Req 3)

1. When 研究者が完了済みジョブの結果詳細を表示した時, the Streamlit UI shall 当該ジョブの可視化アーティファクト（ヒートマップ・マスク・オーバーレイ）のサムネイル一覧を表示する
2. When 研究者がサムネイルを選択した時, the Streamlit UI shall 選択された可視化画像を拡大表示する
3. When 研究者が可視化結果を表示した時, the Streamlit UI shall 元画像・ヒートマップ・マスク・オーバーレイを並べて比較できるレイアウトを提供する
4. While ジョブが完了状態である間, the Streamlit UI shall MLflow UIの当該Runのアーティファクトページへのリンクを表示する
5. If 可視化アーティファクトが存在しない場合, the Streamlit UI shall 「可視化結果なし」のメッセージを表示する

### Requirement 4: 可視化アーティファクト取得API

**Objective:** 研究者（API利用）として、可視化アーティファクトの一覧・取得をAPI経由で行えることで、自動化ワークフローに組み込みたい

#### Acceptance Criteria (Req 4)

1. When 研究者がジョブの可視化アーティファクト一覧をリクエストした時, the API shall 当該ジョブの可視化画像ファイル名リストをJSON形式で返却する
2. When 研究者が特定の可視化画像をリクエストした時, the API shall 指定されたファイルの画像データを返却する
3. If 指定されたジョブIDの可視化アーティファクトが存在しない場合, the API shall 404ステータスコードとエラーメッセージを返却する
4. The API shall 可視化アーティファクト取得エンドポイントに認証（Bearer token）を必須とする

### Requirement 5: 異常スコアデータ出力

**Objective:** 研究者として、異常スコアを数値データとして取得できることで、定量分析やSPC（統計的工程管理）に活用したい

#### Acceptance Criteria (Req 5)

1. When Workerがanomalibモデルの評価を完了した時, the Worker shall 画像レベルの予測結果（ファイル名・異常スコア・判定結果）をCSV形式（`image_predictions.csv`）で出力する
2. When Workerがanomalibモデルの評価を完了した時, the Worker shall ピクセルレベルの予測結果をCSV形式（`pixel_predictions.csv`）で出力する
3. The Worker shall CSV出力をアーティファクトディレクトリ（`<artifact_root>/<job_id>/`）に保存し、TrackingPort経由でMLflowに記録する
4. When 研究者がCSVデータをAPIから取得した時, the API shall CSVファイルをダウンロード可能な形式で返却する

### Requirement 6: 可視化設定

**Objective:** 研究者として、可視化の有効・無効や出力対象を制御できることで、必要に応じてリソース消費を最適化したい

#### Acceptance Criteria (Req 6)

1. The Worker shall 可視化アーティファクト生成をデフォルトで有効とする
2. When 投稿者が設定ファイル（config.yaml）で可視化を無効に指定した時, the Worker shall 可視化アーティファクトの生成をスキップする
3. When 投稿者が設定ファイルで可視化対象（heatmap / mask / overlay）を指定した時, the Worker shall 指定された種別のみ生成する
4. If 設定ファイルに可視化設定が含まれていない場合, the Worker shall 全種別（heatmap・mask・overlay）を生成する
