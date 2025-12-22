# API 仕様

LeadersBoard REST API の詳細仕様

## 認証

全てのエンドポイントは `Authorization: Bearer <token>` ヘッダーが必須です。

```http
Authorization: Bearer devtoken
```

トークンは環境変数 `API_TOKENS` で管理されます（カンマ区切り）。

## エンドポイント

### POST /submissions

提出を作成します。

**リクエスト:**

- Content-Type: `multipart/form-data`
- Headers: `Authorization: Bearer <token>`

**パラメータ:**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| files | File[] | ✓ | アップロードファイル（複数可） |
| entrypoint | string | ✓ | エントリポイントファイル名（例: `main.py`） |
| config_file | string | ✓ | 設定ファイル名（例: `config.yaml`） |
| metadata | string | - | メタデータJSON（例: `{"method":"padim"}`） |

**レスポンス:**

```json
{
  "submission_id": "abc123def456"
}
```

**エラー:**

- `400 Bad Request`: バリデーションエラー（ファイルサイズ超過、不正な拡張子等）
- `401 Unauthorized`: 認証トークンが無効
- `429 Too Many Requests`: レート制限超過

**制限:**

- ファイルサイズ: 最大 100MB
- 許可される拡張子: `.py`, `.yaml`, `.zip`, `.tar.gz`
- レート制限: 10提出/時間/ユーザー

---

### POST /jobs

ジョブを投入します。

**リクエスト:**

- Content-Type: `application/json`
- Headers: `Authorization: Bearer <token>`

**ボディ:**

```json
{
  "submission_id": "abc123def456",
  "config": {
    "resource_class": "medium"
  }
}
```

**パラメータ:**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| submission_id | string | ✓ | 提出ID |
| config | object | ✓ | ジョブ設定 |
| config.resource_class | string | - | リソースクラス（`small`: 30分, `medium`: 60分） |

**レスポンス:**

```json
{
  "job_id": "xyz789",
  "status": "pending"
}
```

**エラー:**

- `400 Bad Request`: submission_id が存在しない
- `401 Unauthorized`: 認証トークンが無効
- `429 Too Many Requests`: 同時実行制限超過（最大3件）

---

### GET /jobs/{job_id}/status

ジョブの状態を取得します。

**リクエスト:**

- Headers: `Authorization: Bearer <token>`

**レスポンス:**

```json
{
  "job_id": "xyz789",
  "submission_id": "abc123def456",
  "user_id": "devtoken",
  "status": "running",
  "run_id": "mlflow-run-id",
  "created_at": "2025-12-22T10:00:00Z",
  "updated_at": "2025-12-22T10:05:00Z"
}
```

**ステータス:**

- `pending`: キュー待機中
- `running`: 実行中
- `completed`: 完了
- `failed`: 失敗（`error` フィールドにエラーメッセージ）

**エラー:**

- `404 Not Found`: job_id が存在しない
- `401 Unauthorized`: 認証トークンが無効

---

### GET /jobs/{job_id}/logs

ジョブのログを取得します。

**リクエスト:**

- Headers: `Authorization: Bearer <token>`

**レスポンス:**

```text
[2025-12-22 10:00:00] Starting job xyz789
[2025-12-22 10:01:00] Loading dataset...
[2025-12-22 10:02:00] Training model...
[2025-12-22 10:05:00] Job completed
```

**エラー:**

- `404 Not Found`: ログファイルが存在しない
- `401 Unauthorized`: 認証トークンが無効

---

### GET /jobs/{job_id}/results

ジョブの結果を取得します（MLflow リンク含む）。

**リクエスト:**

- Headers: `Authorization: Bearer <token>`

**レスポンス:**

```json
{
  "job_id": "xyz789",
  "run_id": "mlflow-run-id",
  "mlflow_ui_link": "http://mlflow:5010/#/experiments/1/runs/mlflow-run-id",
  "mlflow_rest_link": "http://mlflow:5010/api/2.0/mlflow/runs/get?run_id=mlflow-run-id"
}
```

**エラー:**

- `404 Not Found`: job_id が存在しない、または run_id がまだ生成されていない
- `401 Unauthorized`: 認証トークンが無効

---

## OpenAPI 仕様

FastAPI が自動生成する OpenAPI 仕様は以下で確認できます：

- Swagger UI: `http://localhost:8010/docs`
- ReDoc: `http://localhost:8010/redoc`
- OpenAPI JSON: `http://localhost:8010/openapi.json`

## エラーレスポンス形式

全てのエラーレスポンスは以下の形式に従います：

```json
{
  "detail": "エラーメッセージ"
}
```

## レート制限

### 提出制限

- **制限**: 10提出/時間/ユーザー
- **実装**: Redis カウンター（TTL 3600秒）
- **超過時**: `429 Too Many Requests`

### 同時実行制限

- **制限**: 3ジョブ/ユーザー
- **実装**: Redis による running 状態カウント
- **超過時**: `429 Too Many Requests`

## 投稿者のコード規約

投稿者のコードは以下のインタフェースに従う必要があります：

### エントリポイント

```python
# main.py
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    # 学習・評価を実行
    # ...
    
    # 結果を metrics.json に出力
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    metrics = {
        "params": {
            "method": "padim",
            "dataset": "mvtec_ad",
            "backbone": "resnet18"
        },
        "metrics": {
            "image_auc": 0.985,
            "pixel_auc": 0.976,
            "pixel_pro": 0.920
        }
    }
    
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

if __name__ == "__main__":
    main()
```

### metrics.json フォーマット

```json
{
  "params": {
    "method": "padim",
    "dataset": "mvtec_ad",
    "backbone": "resnet18"
  },
  "metrics": {
    "image_auc": 0.985,
    "pixel_auc": 0.976,
    "pixel_pro": 0.920
  }
}
```

**重要**: 投稿者のコードは MLflow に直接依存しません。Worker が `metrics.json` を読み取り、MLflow に記録します。
