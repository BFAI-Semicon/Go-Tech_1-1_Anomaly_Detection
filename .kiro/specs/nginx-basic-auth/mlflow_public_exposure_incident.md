# MLflow 公開事故

MLflow 公開事故は、**MLOps 環境特有の「管理系サービス露出」事故**の典型例です。
初心者向けに全体像 → 技術的詳細 → 再発防止の順で整理します。

---

## 1. 何が起きる事故か（概要）

### 一言定義

> インターネットに公開された MLflow Tracking Server が
> 認証なし（または弱い認証）でアクセス可能になり、
> 実験データ・モデル・認証情報が漏洩／改ざんされる事故

---

## 2. MLflow が狙われる理由

MLflow は単なるログツールではなく、以下を持ちます。

| 資産 | 価値 |
| --- | --- |
| 学習データパス | 機密データ位置 |
| モデル | 知財 |
| パラメータ | 再現性・ノウハウ |
| Artifact | 重み・特徴量 |
| 環境変数 | APIキー等 |

つまり攻撃者視点では：

* AI知財
* クラウド資格情報
* 社内パス構造

が一括取得可能。

---

## 3. 典型的な公開事故構成

最も多い構成：

```text
MLflow Tracking Server
  ├ backend-store (PostgreSQL / SQLite)
  ├ artifact-store (S3 / MinIO / NFS)
  └ UI (5000/5010 port)
```

事故原因：

* `0.0.0.0` bind
* Firewall未設定
* 認証なし
* Reverse proxyなし

---

## 4. 何が見えるのか（実被害イメージ）

公開状態だとブラウザから：

### ① 実験一覧

* Project名
* User名
* Run履歴

### ② ハイパーパラメータ

```text
learning_rate=0.001
batch_size=64
dataset=/mnt/data/customer_A/
```

→ 顧客名やデータ構造露出

### ③ Artifact ダウンロード

取得可能：

* `model.pt`
* `model.onnx`
* `scaler.pkl`
* `label_map.json`

→ モデル完全流出

### ④ 環境情報

```text
MLFLOW_S3_ENDPOINT_URL
AWS_ACCESS_KEY_ID
```

→ クラウド侵害へ横展開

---

## 5. 攻撃フロー（実際）

```text
1. Shodan / Censys 検索
   "mlflow" "experiment"
2. 公開UI発見
3. Artifact一覧取得
4. モデルDL
5. Credential探索
6. S3 / DB侵入
```

探索は完全自動化済み。

---

## 6. 実際に起きた被害例（類型）

※特定企業名は非公開事例多

### パターンA：モデル窃取

* 外販AIモデル流出
* 推論APIコピー

### パターンB：顧客データ漏洩

* Artifactに学習画像保存
* 個人情報混入

### パターンC：クラウド侵害

* MLflow env から AWS Key 流出
* S3 全取得

### パターンD：改ざん

* Run削除
* 指標書き換え

---

## 7. なぜ公開されるのか（根本原因）

### ① 開発用のまま本番化

```bash
mlflow ui --host 0.0.0.0
```

→ そのままクラウド配置

---

### ② Docker Compose 露出

```yaml
ports:
  - "5010:5000"
```

* Security Group 全開放

---

### ③ 認証機構が標準非搭載

MLflow 単体には：

* Login
* RBAC
* Token auth

が基本なし。

---

### ④ Artifact に機密混入

例：

* `/mnt/nfs/customerA/raw/`
* `/data/semicon_line3/`

---

## 8. セキュリティ影響度

CVSS 的に見ると：

| 観点 | 影響 |
| --- | --- |
| 機密性 | 極大 |
| 完全性 | 中 |
| 可用性 | 低 |
| 横展開 | 極大 |

AI企業では**知財流出＝事業損失**。

---

## 9. 再発防止アーキテクチャ

### 必須対策

#### ① 非公開ネットワーク

* VPC 内限定
* VPN 経由

---

#### ② Reverse Proxy + 認証

例：

* Nginx
* Traefik
* Cloudflare Access

Basic Auth 最低限。

---

#### ③ ポート閉鎖

```text
0.0.0.0 → 127.0.0.1
```

---

#### ④ Artifact 分離

* 機密データ保存禁止
* 重みのみ

---

#### ⑤ IAM 最小権限

MLflow 用 Key：

* 読取専用
* Bucket限定

---

## 10. 安全な公開構成（推奨）

```text
Internet
   ↓
WAF / Access Gateway
   ↓
Reverse Proxy (Auth)
   ↓
MLflow (Private Subnet)
   ↓
DB / Artifact Store
```

---

## 11. MLOps 環境特有の注意点

あなたのような構成（GPU / Docker / MLflow / NFS）では特に：

### リスク増幅要因

* NFS Artifact
* 社内データ直参照
* 自動学習ログ
* env 変数露出

---

## 12. 監査チェックリスト

簡易診断：

```text
□ MLflow が Internet から見える
□ 認証なし
□ Artifact に画像保存
□ AWS Key を env 使用
□ 5000/5010 ポート公開
□ Shodan に検出
```

1つでも該当 → 要是正。

---

## 13. まとめ（初心者向け要約）

* MLflow は「AI開発の司令塔」
* 公開すると：

  * モデル
  * データ
  * 認証情報
    が一括露出
* 標準で認証なし
* 開発設定のまま公開が主因
