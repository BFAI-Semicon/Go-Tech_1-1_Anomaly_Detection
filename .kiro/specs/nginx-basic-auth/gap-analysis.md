# Gap Analysis: nginx-basic-auth

## 分析サマリー

- 現状は `mlflow` と `streamlit` が `ports` で外部公開されており、要件の入口集約と不一致。
- API の Bearer 認証は実装済みで、Nginx 導入後も API 側ロジック変更は最小で済む。
- 主要ギャップはインフラ層（compose、Nginx 設定、運用手順、デプロイ反映）に集中する。
- サブパス運用の成立条件は Streamlit `baseUrlPath` と WebSocket 転送である。
- 本件は既存拡張型で、実装は Option C（Hybrid）が最も現実的。

## Requirement-to-Asset Map

- **1.x**
  - 既存資産: `LeadersBoard/docker-compose.yml`
  - 状態: Missing
  - ギャップ: Nginx サービス未定義で、`mlflow`/`streamlit` が外部公開中。
- **2.x**
  - 既存資産: なし（Nginx 設定未実装）
  - 状態: Missing
  - ギャップ: `/mlflow/` の Basic 認証、ヘッダー転送、サブパス制御が未実装。
- **3.x**
  - 既存資産: `LeadersBoard/src/streamlit/app.py`
  - 状態: Constraint
  - ギャップ: API トークン入力は実装済み。Nginx 側 WS 中継とサブパス設定が必要。
- **4.x**
  - 既存資産: `.env.example`
  - 状態: Missing
  - ギャップ: `htpasswd` 生成・更新運用手順が未記載。
- **5.x**
  - 既存資産: devcontainer 設定と deploy workflow
  - 状態: Constraint
  - ギャップ: dev/prod 互換を保ちながら Nginx 組み込みが必要。
- **6.x**
  - 既存資産: なし（Nginx runtime 設定未実装）
  - 状態: Missing
  - ギャップ: body size、timeout、ログ出力の運用設定が未実装。

## 実装アプローチの選択肢

### Option A: 既存構成の拡張中心

- compose と deploy の既存ファイルに Nginx 定義を追記し、`nginx/` 設定を追加。
- **利点**: 変更点が集中し、既存運用フローを保ちやすい。
- **懸念**: 既存 compose の責務が肥大化しやすい。

### Option B: 新規構成分離中心

- Nginx 専用 compose オーバーレイや専用運用ドキュメントを分離追加。
- **利点**: 役割分離が明確で保守しやすい。
- **懸念**: ファイル数増加とデプロイ手順分岐が発生する。

### Option C: Hybrid（推奨）

- 既存 compose/deploy を拡張しつつ、`nginx/` と認証運用手順は新規追加で分離。
- **利点**: 既存互換性と責務分離のバランスが最良。
- **懸念**: 変更対象が複数層にまたがるため、試験観点の整理が必須。

## 既知の制約と Research Needed

- **制約**: Streamlit Docker 起動に `server.baseUrlPath` 指定が未実装。
- **制約**: MLflow のサブパス運用はバージョン差分の影響を受けやすい。
- **Research Needed**:
  - `/mlflow/` 配下で UI と API を両立する rewrite 方針の最終確定
  - cloudflared 公開 URL と Nginx host/path 設計の運用手順
  - 認証情報更新時の安全なローテーション手順

## 複雑度とリスク

- **Effort**: M（3-7日）
  - 理由: アプリ改修は小さいが、compose・Nginx・deploy・運用文書の横断変更が必要。
- **Risk**: Medium
  - 理由: 技術は既知だが、サブパスと WebSocket の設定不整合で機能退行が起きやすい。

## デザインフェーズへの提言

- 入口認証とアプリ内認可の境界をインタフェース契約として明文化する。
- 受け入れ試験は「401/200」「サブパス表示」「WS 更新」「MLflow 遷移」を最小セット化する。
- Option C を基準に、Nginx 設定責務と compose/deploy 変更責務を分離して設計する。
