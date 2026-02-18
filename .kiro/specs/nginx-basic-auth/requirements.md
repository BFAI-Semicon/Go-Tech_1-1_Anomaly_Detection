# Requirements Document

## Introduction

LeadersBoard プラットフォームでは、
MLflow Tracking Server（ポート5010）と Streamlit UI（ポート8501）が
docker-compose 経由で直接公開されており、認証なしでアクセス可能な状態にある。
MLflow には実験データ・モデル・パラメータ・アーティファクトが蓄積されており、
無防備な公開は知財漏洩・クラウド侵害のリスクを伴う。

本仕様では、Nginx リバースプロキシを前段に配置し、
同一ホスト配下のパス分割（`/mlflow/` と `/streamlit/`）で
MLflow UI と Streamlit UI を公開する。
両パスに Basic 認証を適用し、同一オリジンでの運用により
認証体験と運用管理を統一する。
FastAPI（ポート8010）は既に独自のトークン認証を持つため、
Nginx の保護対象外とする。

## Requirements

### Requirement 1: Nginx リバースプロキシの導入

**Objective:** インフラ管理者として、
Nginx をリバースプロキシとして docker-compose に追加したい。
これにより、MLflow と Streamlit への直接アクセスを遮断し、
認証付きの単一エントリポイントを提供できる。

#### Acceptance Criteria 1

1. The docker-compose shall Nginx サービスを定義し、
   既存サービス（api, worker, redis, mlflow, streamlit）と
   同一ネットワーク上で動作させる
2. The Nginx サービス shall 外部向けポート（80 番）をリッスンし、
   認証付きリクエストを内部サービスに転送する
3. The Nginx shall 同一ホスト配下で
   `/mlflow/` を MLflow、`/streamlit/` を Streamlit に
   ルーティングする
4. The MLflow サービス shall `ports` を削除し、
   `expose` のみで内部ネットワークに限定する
   （外部から直接アクセス不可）
5. The Streamlit サービス shall `ports` を削除し、
   `expose` のみで内部ネットワークに限定する
   （外部から直接アクセス不可）
6. The API サービス shall 既存の `ports: "8010:8010"` を維持する
   （独自トークン認証が存在するため Nginx の保護対象外）

### Requirement 2: Basic 認証による MLflow UI の保護

**Objective:** 管理者として、MLflow UI に Basic 認証を設けたい。
これにより、認証済みユーザーのみが実験データ・モデル・
アーティファクトにアクセスでき、知財漏洩リスクを低減できる。

#### Acceptance Criteria 2

1. When 未認証のリクエストが `/mlflow/` パスに到達した場合,
   the Nginx shall HTTP 401 レスポンスを返し、
   Basic 認証ダイアログを表示する
2. When 正しい認証情報が提供された場合,
   the Nginx shall リクエストを MLflow（内部ポート5010）に
   プロキシ転送する
3. The Nginx shall `htpasswd` ファイルを認証情報のソースとして使用する
4. The Nginx shall MLflow UI のすべてのパス
   （API エンドポイント含む）を認証対象とする
5. The Nginx shall `proxy_set_header`
   （Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto）を設定し、
   MLflow が正しいクライアント情報を受け取れるようにする
6. The Nginx shall MLflow をサブパス運用できるように設定し、
   `/mlflow/` 配下で静的リソース・API が正常動作する

### Requirement 3: Basic 認証による Streamlit UI の保護

**Objective:** 管理者として、Streamlit UI にも Basic 認証を設けたい。
これにより、認証済みユーザーのみがジョブ投入・監視機能にアクセスできる。
また、既存の Streamlit 内トークン入力フローと併用し、
段階的なアクセス制御（入口認証 + アプリ内認可）を維持する。

#### Acceptance Criteria 3

1. When 未認証のリクエストが `/streamlit/` パスに到達した場合,
   the Nginx shall HTTP 401 レスポンスを返し、
   Basic 認証ダイアログを表示する
2. When 正しい認証情報が提供された場合,
   the Nginx shall リクエストを Streamlit（内部ポート8501）に
   プロキシ転送する
3. The Nginx shall MLflow と Streamlit で同一の `htpasswd` ファイルを共有する
4. The Nginx shall Streamlit の WebSocket 接続
   （`/_stcore/stream`）を正しくプロキシする
   （`Upgrade` / `Connection` ヘッダー転送）
5. When Basic 認証を通過して Streamlit UI にアクセスした場合,
   the Streamlit shall 既存のトークン入力と検証フローを変更せず維持する
6. The システム shall Basic 認証を「ネットワーク境界の入口認証」、
   Streamlit トークンを「アプリ内操作の認可」として扱い、
   どちらか一方のみでジョブ投入可能にならないようにする
7. The Streamlit shall サブパス `/streamlit/` で表示崩れなく動作し、
   必要なベースパス設定（例: `server.baseUrlPath`）を反映する

### Requirement 4: htpasswd ファイル管理

**Objective:** インフラ管理者として、
認証用ユーザー・パスワードを安全に管理したい。
これにより、認証情報の作成・更新を標準的な手順で行える。

#### Acceptance Criteria 4

1. The プロジェクト shall `htpasswd` ファイルを
   git 管理外（`.gitignore`）とし、
   認証情報をリポジトリに含めない
2. The プロジェクト shall `.env.example` に `htpasswd` 作成手順を記載する
3. The プロジェクト shall `htpasswd` コマンドまたは
   Docker ベースの代替手順を文書化する
4. If `htpasswd` ファイルが存在しない場合,
   the Nginx shall 起動に失敗し、エラーログに原因を出力する

### Requirement 5: 既存環境との互換性

**Objective:** 開発者として、
Nginx 導入後も devcontainer 環境と本番デプロイが正常に動作してほしい。
これにより、開発ワークフローの中断を防げる。

#### Acceptance Criteria 5

1. The devcontainer 構成 shall Nginx 導入後も
   `api` サービスへの接続が正常に動作する
2. The docker-compose.prod.yml shall
   Nginx サービスのプリビルドイメージまたはビルド定義を含む
3. The deploy.yml（CD パイプライン） shall
   Nginx を含むデプロイが正常に動作する
4. The Nginx 設定ファイル shall `nginx/` ディレクトリにまとめ、
   docker-compose からボリュームマウントする
5. When devcontainer 内から MLflow UI にアクセスする場合,
   the 開発者 shall Nginx 経由（ポート80）または
   直接（内部ネットワーク経由）のどちらでもアクセスできる
6. The 公開 URL 設計 shall 同一ホスト配下の
   `/mlflow/` と `/streamlit/` を前提とし、
   cloudflared tunnel の HTTPS 終端構成と整合する

### Requirement 6: Nginx 設定のベストプラクティス

**Objective:** インフラ管理者として、
Nginx の設定がセキュリティと運用のベストプラクティスに
従っていてほしい。これにより、安全で安定した
リバースプロキシ環境を維持できる。

#### Acceptance Criteria 6

1. The Nginx shall `client_max_body_size` を適切に設定し、
   アーティファクトアップロードに対応する
2. The Nginx shall `proxy_read_timeout` / `proxy_send_timeout`
   を設定し、長時間の MLflow UI 操作に対応する
3. The Nginx shall アクセスログ・エラーログを標準出力に出力し、
   `docker compose logs` で確認可能にする
4. The Nginx shall `restart: unless-stopped` で自動再起動する
