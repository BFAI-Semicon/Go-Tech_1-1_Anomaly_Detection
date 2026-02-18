# Nginx + MLflow認証構成例

以下は **「Nginx を前段に置いて Basic認証＋（任意で）TLS」**で MLflow Tracking Server を守る、いちばん実用的な構成例です。
ポイントは **MLflow を外に晒さない（portsを公開しない）**こと。

---

## 構成（最小・実戦向け）

* 外部公開：**Nginx のみ（80/443）**
* 内部：Nginx → `mlflow:5000` にプロキシ
* 認証：Nginx Basic認証（まずこれで事故は激減）
* MLflow：`--host 0.0.0.0` でも **内部ネットワーク限定**ならOK

---

## 1) docker-compose.yml（Nginx + MLflow）

```yaml
services:
  nginx:
    image: nginx:1.27-alpine
    container_name: mlflow-nginx
    ports:
      - "80:80"
      # TLSを使うなら:
      # - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/auth:/etc/nginx/auth:ro
      # TLSを使うなら証明書をマウント:
      # - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      - mlflow
    networks:
      - mlops_net

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    container_name: mlflow
    command: >
      bash -lc "
      mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri sqlite:////mlflow/mlflow.db
      --default-artifact-root /mlflow/artifacts
      "
    volumes:
      - mlflow-data:/mlflow
    expose:
      - "5000"   # 外部公開しない（portsを使わない）
    networks:
      - mlops_net

networks:
  mlops_net:
    driver: bridge

volumes:
  mlflow-data:
```

> ✅ **重要**：`mlflow` 側は `ports:` を書かない（= インターネットに公開しない）

---

## 2) Nginx 設定（Basic認証 + 逆プロキシ）

`./nginx/conf.d/mlflow.conf`

```nginx
server {
    listen 80;
    server_name _;

    # --- Basic認証 ---
    auth_basic           "MLflow";
    auth_basic_user_file /etc/nginx/auth/htpasswd;

    # アップロードがある環境なら調整
    client_max_body_size 200m;

    location / {
        proxy_pass http://mlflow:5000;

        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # タイムアウト（重いUIやartifactアクセスで調整）
        proxy_read_timeout  300;
        proxy_send_timeout  300;
    }
}
```

---

## 3) htpasswd（ユーザー/パスワード作成）

Nginx コンテナに入る前に **ホスト側で**作るのが楽です。

### A. `htpasswd` コマンドがある場合

```bash
mkdir -p nginx/auth
htpasswd -c nginx/auth/htpasswd mlopsadmin
# パスワード入力
```

### B. `htpasswd` が無い場合（Dockerで作る）

```bash
mkdir -p nginx/auth
docker run --rm -it -v "$PWD/nginx/auth:/out" httpd:2.4-alpine \
  htpasswd -c /out/htpasswd mlopsadmin
```

---

## 4) 起動・確認

```bash
docker compose up -d
```

ブラウザで `http://<server-ip>/` にアクセス → Basic認証が出ればOK。

---

## TLS（HTTPS）も入れる場合（任意）

本番や社外アクセスがあるなら **HTTPS 推奨**です。

### 追加マウント（compose の nginx に）

```yaml
- ./nginx/certs:/etc/nginx/certs:ro
```

### Nginx 側（例：443 を追加）

```nginx
server {
    listen 443 ssl;
    server_name your.domain.example;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    auth_basic           "MLflow";
    auth_basic_user_file /etc/nginx/auth/htpasswd;

    location / {
        proxy_pass http://mlflow:5000;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Host $host;
    }
}
```

---

## 事故を防ぐための「最低ライン」チェック

* [ ] MLflow サービスに `ports:` がない（外部公開してない）
* [ ] Nginx で認証（少なくとも Basic）
* [ ] 可能なら HTTPS（または Cloudflare Access / VPN）
* [ ] Artifact に機密データ（生画像や認証情報）を置かない
