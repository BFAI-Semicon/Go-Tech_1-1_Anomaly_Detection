# デプロイ手順

LeadersBoard のデプロイ手順書

## 前提条件

### 必須環境

- **Docker**: 20.10以降
- **docker-compose**: 2.0以降
- **NVIDIAドライバ**: GPU使用時は必須
- **nvidia-container-runtime**: GPU使用時は必須

### GPUサポート確認

```bash
# nvidia-smi が動作することを確認
nvidia-smi

# Docker で GPU が認識されることを確認
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

## ローカル環境デプロイ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-org/leaders-board.git
cd leaders-board/LeadersBoard
```

### 2. 環境変数の設定

```bash
# .env ファイルを作成
cp .env.example .env

# .env を編集（必要に応じて）
nano .env
```

**重要な環境変数:**

```bash
# 認証トークン（カンマ区切り）
API_TOKENS=devtoken,token-alice,token-bob

# Redis接続URL
REDIS_URL=redis://redis:6379/0

# MLflow Tracking Server URL
MLFLOW_TRACKING_URI=http://mlflow:5010

# 共有ディレクトリ
UPLOAD_ROOT=/shared/submissions
LOG_ROOT=/shared/logs
ARTIFACT_ROOT=/shared/artifacts

# レート制限設定
MAX_SUBMISSIONS_PER_HOUR=50  # 1時間あたりの最大投稿数
MAX_CONCURRENT_RUNNING=2     # 同時実行ジョブ数
```

### 3. サービスの起動

```bash
# 全サービスを起動
docker-compose up -d

# ログを確認
docker-compose logs -f
```

### 4. 動作確認

```bash
# API ヘルスチェック
curl http://localhost:8010/docs

# Streamlit UI
open http://localhost:8501

# MLflow UI
open http://localhost:5010
```

### 5. 停止とクリーンアップ

```bash
# サービスを停止
docker-compose down

# ボリュームも削除（データが消えます）
docker-compose down -v
```

## 本番環境デプロイ

### アーキテクチャ選択

#### Option 1: シングルノード構成

最小構成。開発・検証環境向け。

```text
┌─────────────────────────────────────┐
│  Docker Host (GPU required)         │
│  ├─ API Container                   │
│  ├─ Worker Container                │
│  ├─ Redis Container                 │
│  ├─ MLflow Container                │
│  └─ Streamlit Container             │
└─────────────────────────────────────┘
```

#### Option 2: マルチノード構成

スケールアウト対応。本番環境向け。

```text
┌─────────────────┐  ┌──────────────────┐
│  API Nodes      │  │  Worker Nodes    │
│  (Load Balanced)│  │  (GPU required)  │
│  ├─ API 1       │  │  ├─ Worker 1     │
│  ├─ API 2       │  │  ├─ Worker 2     │
│  └─ API N       │  │  └─ Worker N     │
└─────────────────┘  └──────────────────┘
         │                    │
         └────────┬───────────┘
                  │
    ┌─────────────────────────────┐
    │  Shared Services            │
    │  ├─ Redis (HA cluster)      │
    │  ├─ MLflow (external DB)    │
    │  └─ S3 (artifact storage)   │
    └─────────────────────────────┘
```

### シングルノード構成のデプロイ

#### 1. サーバー準備

```bash
# Docker と nvidia-container-runtime のインストール
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker

# nvidia-container-runtime のインストール
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-runtime
sudo systemctl restart docker
```

#### 2. デプロイ

```bash
# リポジトリをクローン
git clone https://github.com/your-org/leaders-board.git
cd leaders-board/LeadersBoard

# 環境変数を設定
cp .env.example .env
nano .env

# 本番用でビルド・起動
docker-compose -f docker-compose.yml up -d --build

# ログを確認
docker-compose logs -f
```

#### 3. リバースプロキシ設定（Nginx）

```nginx
# /etc/nginx/sites-available/leaders-board
upstream api_backend {
    server localhost:8010;
}

upstream streamlit_backend {
    server localhost:8501;
}

upstream mlflow_backend {
    server localhost:5010;
}

server {
    listen 80;
    server_name leaders-board.example.com;

    # API
    location /api/ {
        proxy_pass http://api_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Streamlit UI
    location / {
        proxy_pass http://streamlit_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # MLflow UI
    location /mlflow/ {
        proxy_pass http://mlflow_backend/;
        proxy_set_header Host $host;
    }
}
```

```bash
# Nginx を有効化
sudo ln -s /etc/nginx/sites-available/leaders-board /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### マルチノード構成のデプロイ

#### 1. Kubernetes クラスター準備

```bash
# kubectl と helm のインストール
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 2. Helm Chart でデプロイ（将来実装）

```bash
# Helm chart を作成（TODO: T20で実装）
helm install leaders-board ./helm/leaders-board \
  --set redis.enabled=true \
  --set mlflow.externalDatabase=true \
  --set storage.type=s3
```

## データ永続化

### ローカル環境

Docker volumes を使用：

```yaml
volumes:
  shared: # 提出ファイル・アーティファクト
  redis-data: # Redis AOF
```

### 本番環境

#### Option 1: ホストマウント

```yaml
volumes:
  - /mnt/leaderboard/submissions:/shared/submissions
  - /mnt/leaderboard/artifacts:/shared/artifacts
  - /mnt/leaderboard/logs:/shared/logs
```

#### Option 2: S3 互換ストレージ

```bash
# StoragePort の S3Adapter 実装が必要（将来実装）
S3_BUCKET=leaderboard-artifacts
S3_ENDPOINT=https://s3.amazonaws.com
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
```

## バックアップ

### Redis

```bash
# AOF スナップショットを取得
docker-compose exec redis redis-cli BGSAVE

# バックアップをコピー
docker cp $(docker-compose ps -q redis):/data/dump.rdb ./backup/redis-$(date +%Y%m%d).rdb
```

### MLflow データベース

```bash
# SQLite をバックアップ
docker cp $(docker-compose ps -q mlflow):/shared/mlflow.db ./backup/mlflow-$(date +%Y%m%d).db
```

### 提出ファイル・アーティファクト

```bash
# 共有ボリュームをバックアップ
tar czf backup/shared-$(date +%Y%m%d).tar.gz shared/
```

## モニタリング

### ログ収集

```bash
# 全サービスのログ
docker-compose logs -f

# 特定サービスのログ
docker-compose logs -f worker

# ログを保存
docker-compose logs > logs/$(date +%Y%m%d).log
```

### メトリクス

- **Prometheus** + **Grafana** による監視（将来実装）
- **MLflow UI** で実験メトリクスを確認: `http://localhost:5010`

## トラブルシューティング

### Worker がジョブを処理しない

```bash
# Worker ログを確認
docker-compose logs -f worker

# Redis キューを確認
docker-compose exec redis redis-cli LLEN leaderboard:jobs

# Worker を再起動
docker-compose restart worker
```

### Out of Memory エラー

```bash
# Worker のメモリ制限を増やす
# docker-compose.yml
services:
  worker:
    deploy:
      resources:
        limits:
          memory: 16G
```

### GPU が認識されない

```bash
# nvidia-container-runtime が有効か確認
docker info | grep -i runtime

# Worker コンテナで GPU を確認
docker-compose exec worker nvidia-smi
```

## セキュリティ

### 本番環境チェックリスト

- [ ] API_TOKENS を強固なトークンに変更
- [ ] HTTPS を有効化（Let's Encrypt推奨）
- [ ] ファイアウォールで必要なポートのみ開放
- [ ] Redis に認証を設定
- [ ] MLflow に認証を追加（将来実装）
- [ ] 定期的なバックアップを設定
- [ ] ログローテーションを設定
- [ ] セキュリティアップデートを定期的に適用

## パフォーマンスチューニング

### Redis

```bash
# AOF永続化を有効化
appendonly yes
appendfsync everysec
```

### Worker

```bash
# Worker数を増やす
docker-compose up -d --scale worker=3
```

### API

```bash
# uvicorn workers を増やす（本番用）
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "4"]
```

## 次のステップ

- [ ] Kubernetes Helm Chart の作成
- [ ] Prometheus + Grafana の統合
- [ ] S3 StorageAdapter の実装
- [ ] MLflow 認証の追加
- [ ] CI/CD パイプラインの構築
