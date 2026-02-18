# Implementation Tasks

## Task 1: Nginx 設定ファイルの作成

`LeadersBoard/nginx/` ディレクトリに Nginx リバースプロキシの設定一式を作成する。
Basic 認証、パスルーティング（`/mlflow/` と `/streamlit/`）、WebSocket 転送、
ヘッダー転送、ランタイム設定（body size、timeout、ログ）、および
`htpasswd` 存在チェック付きエントリポイントスクリプトを含む。

**Requirements**: 1.2, 1.3, 2.1, 2.2, 2.4, 2.5, 2.6, 3.1, 3.2, 3.4,
4.4, 5.4, 6.1, 6.2, 6.3

**Files to Create**:

- `LeadersBoard/nginx/conf.d/default.conf`
- `LeadersBoard/nginx/entrypoint.sh`

**Steps**:

1. `LeadersBoard/nginx/conf.d/default.conf` を作成する。
   - `server` ブロックで `listen 80` を設定する。
   - `auth_basic "LeadersBoard"` と
     `auth_basic_user_file /etc/nginx/auth/htpasswd` を
     サーバーレベルで設定する。
   - `client_max_body_size 200m` を設定する。
   - `proxy_read_timeout 300` と `proxy_send_timeout 300` を設定する。
   - `access_log /dev/stdout` と `error_log /dev/stderr` を設定する。
   - `location /mlflow/` ブロックを作成する。
     - `rewrite ^/mlflow/(.*)$ /$1 break` でサブパスを除去する。
     - `proxy_pass http://mlflow:5010/` で MLflow に転送する。
     - `proxy_set_header` で Host、X-Real-IP、X-Forwarded-For、
       X-Forwarded-Proto を設定する。
     - `proxy_http_version 1.1` を設定する。
   - `location /streamlit/` ブロックを作成する。
     - `proxy_pass http://streamlit:8501/streamlit/` で
       Streamlit に転送する。
     - `proxy_set_header` で Host、X-Real-IP、X-Forwarded-For、
       X-Forwarded-Proto を設定する。
     - `proxy_http_version 1.1` を設定する。
     - `proxy_set_header Upgrade $http_upgrade` を設定する。
     - `proxy_set_header Connection "upgrade"` を設定する。
   - ルート `/` へのアクセスを `/streamlit/` にリダイレクトする。
2. `LeadersBoard/nginx/entrypoint.sh` を作成する。
   - `htpasswd` ファイル `/etc/nginx/auth/htpasswd` の
     存在と読み取り可否を確認する。
   - 不在または読み取り不可の場合、
     `htpasswd missing or unreadable` を出力し
     終了コード 1 で終了する。
   - 確認成功後、`exec nginx -g 'daemon off;'` で Nginx を起動する。
   - `chmod +x` で実行権限を付与する。

**Done when**:

- [ ] `nginx/conf.d/default.conf` が `/mlflow/` と `/streamlit/` の両方を定義している
- [ ] Basic 認証が両パスに適用されている
- [ ] WebSocket ヘッダー（Upgrade/Connection）が Streamlit パスで転送される
- [ ] MLflow パスで rewrite が設定されている
- [ ] `entrypoint.sh` が htpasswd 不在時に終了コード 1 で失敗する
- [ ] ログが標準出力に設定されている

---

## Task 2: docker-compose.yml の更新

`LeadersBoard/docker-compose.yml` に Nginx サービスを追加し、
`mlflow` と `streamlit` の `ports` を `expose` に変更して
直接外部公開を停止する。API の `ports: "8010:8010"` は維持する。

**Requirements**: 1.1, 1.4, 1.5, 1.6, 6.4

**Files to Modify**: `LeadersBoard/docker-compose.yml`

**Steps**:

1. `services` に `nginx` サービスを追加する。
   - `image: nginx:1.27-alpine`
   - `ports: "80:80"`
   - `volumes`:
     - `./nginx/conf.d:/etc/nginx/conf.d:ro`
     - `./nginx/auth:/etc/nginx/auth:ro`
     - `./nginx/entrypoint.sh:/etc/nginx/entrypoint.sh:ro`
   - `entrypoint: ["/bin/sh", "/etc/nginx/entrypoint.sh"]`
   - `depends_on: [mlflow, streamlit]`
   - `restart: unless-stopped`
2. `mlflow` サービスの `ports: "5010:5010"` を
   `expose: ["5010"]` に変更する。
3. `streamlit` サービスの `ports: "8501:8501"` を
   `expose: ["8501"]` に変更する。
4. `api` サービスの `ports: "8010:8010"` が
   維持されていることを確認する。

**Done when**:

- [ ] Nginx サービスがポート 80 で定義されている
- [ ] MLflow が `expose` のみで外部公開されていない
- [ ] Streamlit が `expose` のみで外部公開されていない
- [ ] API が `ports: "8010:8010"` を維持している
- [ ] Nginx が `restart: unless-stopped` で定義されている

---

## Task 3: Streamlit サブパス対応

Streamlit を `/streamlit/` サブパスで動作させるため、
Dockerfile の起動コマンドに `--server.baseUrlPath /streamlit/` を追加する。
既存のトークン入力フローと MLflow リンク生成は維持する。

**Requirements**: 3.5, 3.7

**Files to Modify**: `LeadersBoard/docker/streamlit.Dockerfile`

**Steps**:

1. `streamlit.Dockerfile` の `CMD` を更新する。
   - `--server.baseUrlPath` を `/streamlit/` に設定する。
   - 変更後:
     `CMD ["streamlit", "run", "src/streamlit/app.py",
     "--server.port", "8501",
     "--server.address", "0.0.0.0",
     "--server.baseUrlPath", "/streamlit/"]`
2. `build_mlflow_run_link` 関数の動作を確認する。
   - `MLFLOW_URL` 環境変数で外部公開パスを渡す設計のため、
     関数自体の変更は不要。
3. 既存のトークン入力フローが影響を受けないことを確認する。

**Done when**:

- [ ] Streamlit が `--server.baseUrlPath /streamlit/` で起動する
- [ ] 既存のトークン入力フローが変更されていない
- [ ] `build_mlflow_run_link` が正しいパスを生成する

---

## Task 4: htpasswd 管理と認証情報の運用整備

`htpasswd` ファイルの Git 管理外運用を設定し、
作成手順を `.env.example` に記載する。
`.gitignore` に認証ファイルディレクトリを追加する。

**Requirements**: 2.3, 3.3, 4.1, 4.2, 4.3

**Files to Modify**:

- `LeadersBoard/.env.example`
- `/app/.gitignore`

**Steps**:

1. `/app/.gitignore` に以下を追加する。
   - `nginx/auth/`（htpasswd ファイルを追跡しない）
2. `LeadersBoard/.env.example` を更新する。
   - `MLFLOW_URL` の値を `/mlflow` に更新する。
   - `htpasswd` 作成手順をコメントで追記する。
     - `htpasswd` コマンドによる作成手順を記載する。
     - Docker ベースの代替手順を記載する。

**Done when**:

- [ ] `nginx/auth/` が `.gitignore` に含まれている
- [ ] `.env.example` に `htpasswd` 作成手順が記載されている
- [ ] Docker ベースの代替手順が記載されている
- [ ] `MLFLOW_URL` が `/mlflow` に更新されている

---

## Task 5: 本番デプロイ構成の更新

`docker-compose.prod.yml` に Nginx サービスのオーバーライドを追加し、
`deploy.yml` ワークフローに `htpasswd` の配置確認ステップを追加する。

**Requirements**: 5.2, 5.3

**Files to Modify**:

- `LeadersBoard/docker-compose.prod.yml`
- `.github/workflows/deploy.yml`

**Steps**:

1. `docker-compose.prod.yml` に `nginx` サービスを追加する。
   - 本番用の `htpasswd` パスをマウントする。
   - `${NGINX_AUTH_DIR:-./nginx/auth}` を
     `/etc/nginx/auth:ro` にマウントする。
2. `deploy.yml` に `htpasswd` 存在確認ステップを追加する。
   - `/etc/leadersboard/nginx/auth/htpasswd` の存在を確認する。
   - 不在時はワークフローを失敗させる。
   - `.env` に `NGINX_AUTH_DIR=/etc/leadersboard/nginx/auth` を追記する。

**Done when**:

- [ ] `docker-compose.prod.yml` に Nginx サービスが定義されている
- [ ] 本番環境の `htpasswd` パスがマウント可能である
- [ ] `deploy.yml` が `htpasswd` の存在を検証する
- [ ] デプロイコマンドが既存の compose 引数で正常動作する

---

## Task 6: devcontainer 互換性対応

devcontainer 構成を更新して、Nginx 導入後も
開発ワークフローが維持されるようにする。
ポート 80 のフォワーディングを追加し、既存の API 直接アクセスを維持する。

**Requirements**: 5.1, 5.5

**Files to Modify**: `.devcontainer/devcontainer.json`

**Steps**:

1. `devcontainer.json` の `forwardPorts` にポート 80 を追加する。
   - 既存の 8010、5010、6379 に 80 を追加する。
2. `portsAttributes` にポート 80 の設定を追加する。
   - `label: "Nginx Gateway"`
   - `onAutoForward: "notify"`
3. 既存の MLflow（5010）と Redis（6379）の
   フォワーディングは維持する。
   - devcontainer 内では Nginx 経由（80）と
     直接（内部ネットワーク）の両方でアクセス可能。

**Done when**:

- [ ] ポート 80 が `forwardPorts` に含まれている
- [ ] 既存のポート（8010、5010、6379）が維持されている
- [ ] `portsAttributes` にポート 80 のラベルが設定されている

---

## Task 7: Streamlit の MLFLOW_URL 環境変数の更新

docker-compose の Streamlit サービスに設定する `MLFLOW_URL` 環境変数を
Nginx 経由の公開パスに更新する。これにより、Streamlit が生成する
MLflow run リンクがブラウザから Nginx 経由でアクセス可能になる。

**Requirements**: 3.5, 3.7

**Files to Modify**: `LeadersBoard/docker-compose.yml`

**Steps**:

1. `streamlit` サービスの `MLFLOW_URL` デフォルト値を更新する。
   - 現在: `${MLFLOW_URL:-http://mlflow:5010}`
   - 変更後: `${MLFLOW_URL:-/mlflow}`
   - ブラウザから見た相対パスを使うことで、
     ホスト名やプロトコルに依存しないリンクを生成する。

**Done when**:

- [ ] `MLFLOW_URL` のデフォルト値が `/mlflow` になっている
- [ ] `build_mlflow_run_link` が正しいパスを生成する

---

## Task 8: ドキュメント・ステアリング更新

steering ファイルと仕様ステータスを更新し、
Nginx 導入に伴う構成変更を反映する。

**Requirements**: 3.6, 5.6

**Files to Modify**:

- `.kiro/steering/structure.md`
- `.kiro/steering/tech.md`
- `.kiro/specs/nginx-basic-auth/spec.json`

**Steps**:

1. `structure.md` の Docker 構成セクションを更新する。
   - `LeadersBoard/nginx/` ディレクトリの説明を追加する。
   - Nginx サービスの概要を Docker 構成セクションに追記する。
2. `tech.md` を更新する。
   - Architecture セクションに Nginx リバースプロキシの記述を追加する。
   - 二層認証モデル（Basic 認証 + Bearer トークン）の説明を追加する。
   - docker-compose 構成例を Nginx を含む形に更新する。
3. `spec.json` の `phase` を `tasks-generated` に更新し、
   `tasks.generated` を `true` に設定する。

**Done when**:

- [ ] `structure.md` に Nginx ディレクトリとサービスの記述がある
- [ ] `tech.md` に二層認証モデルの記述がある
- [ ] `spec.json` が `tasks-generated` フェーズになっている

---

## Task 9: 統合検証

全タスク完了後に、Nginx を含む構成が正常動作することを手動検証する。
compose 起動、認証、パスルーティング、WebSocket、
既存機能の互換性を確認する。

**Requirements**: 全要件の受け入れ基準を横断的に検証

**Steps**:

1. `htpasswd` テストファイルを作成する。
   - `cd LeadersBoard && mkdir -p nginx/auth`
   - `docker run --rm httpd:2.4-alpine htpasswd -nbB testuser testpass > nginx/auth/htpasswd`
2. `docker compose up -d` で全サービスを起動する。
3. 以下を確認する。
   - 未認証で `http://localhost:80/mlflow/` にアクセスし
     401 が返ること。
   - 認証後に MLflow UI が表示されること。
   - 未認証で `http://localhost:80/streamlit/` にアクセスし
     401 が返ること。
   - 認証後に Streamlit UI が表示されること。
   - Streamlit のトークン入力フローが動作すること。
   - `http://localhost:8010` で API が直接アクセスできること。
   - MLflow `5010` と Streamlit `8501` が
     外部からアクセスできないこと。
4. `htpasswd` を削除して Nginx が起動失敗することを確認する。
   - エラーログに `htpasswd missing or unreadable` が
     出力されること。
   - 終了コードが 1 であること。
5. compose を停止する。

**Done when**:

- [ ] 未認証で `/mlflow/` と `/streamlit/` が 401 を返す
- [ ] 認証後に MLflow UI と Streamlit UI が正常表示される
- [ ] API が `8010` で直接アクセスできる
- [ ] MLflow と Streamlit が外部から直接アクセスできない
- [ ] `htpasswd` 不在時に Nginx が起動失敗する
- [ ] Streamlit の既存トークンフローが動作する
