# Research & Design Decisions

## Summary

- **Feature**: `nginx-basic-auth`
- **Discovery Scope**: Extension
- **Key Findings**:
  - 既存の `docker-compose.yml` は `mlflow` と `streamlit` を直接公開している。
  - Streamlit のサブパス運用は `server.baseUrlPath` と WebSocket 転送が要点になる。
  - MLflow のサブパス運用は Nginx 側のパス制御を設計で明確化する必要がある。

## Research Log

### 既存システムの統合ポイント

- **Context**: 既存機能を壊さず Nginx を追加できるか確認した。
- **Sources Consulted**:
  - `LeadersBoard/docker-compose.yml`
  - `LeadersBoard/docker-compose.prod.yml`
  - `LeadersBoard/src/streamlit/app.py`
  - `.kiro/steering/tech.md`
- **Findings**:
  - `api` は `8010` 公開を維持できる。既存 Bearer 認証があるため要件と整合。
  - `mlflow` と `streamlit` は `ports` 公開中で、`expose` 化が必要。
  - Streamlit は `MLFLOW_URL` で run リンクを構築するため、公開 URL 変更に追従が必要。
- **Implications**:
  - compose 境界変更が主要設計要素となる。
  - UI リンク整合を要件化しないと遷移不整合リスクが残る。

### Streamlit のサブパスと WebSocket 要件

- **Context**: `/streamlit/` 配下で UI と自動更新が動く条件を確認した。
- **Sources Consulted**:
  - Streamlit 関連調査（reverse proxy, baseUrlPath, websocket）
- **Findings**:
  - `server.baseUrlPath` がサブパス運用の前提になる。
  - Nginx は `proxy_http_version 1.1` と `Upgrade`/`Connection` 転送が必要。
  - `/streamlit/` の末尾スラッシュを前提にする運用が安定しやすい。
- **Implications**:
  - Nginx と Streamlit 設定をペアで管理する設計が必要。
  - WebSocket 疎通を受け入れ試験に明記する。

### MLflow のサブパス運用制約

- **Context**: `/mlflow/` で UI と API の双方を安定公開できるか調査した。
- **Sources Consulted**:
  - MLflow 関連調査（reverse proxy, static prefix）
  - `.kiro/specs/nginx-basic-auth/nginx_mlflow_auth_config.md`
- **Findings**:
  - `static-prefix` のみでは環境差分を吸収しきれないケースがある。
  - Nginx 側の rewrite とヘッダー制御を設計で固定化する必要がある。
- **Implications**:
  - MLflow 側設定と Nginx 側設定の責務境界を明確化する。
  - UI だけでなく API 疎通を含む検証が必要。

### Basic 認証と HTTPS 区間

- **Context**: cloudflared tunnel 配下で Basic 認証の安全性を確認した。
- **Sources Consulted**:
  - Nginx 公式 `auth_basic` ドキュメント
  - 要件と運用前提（cloudflared HTTPS）
- **Findings**:
  - Basic 認証は `Authorization` ヘッダーで送るが HTTPS 区間では TLS で保護される。
  - 同一ホスト配下の公開では認証再利用により再入力頻度を低減できる。
- **Implications**:
  - 同一オリジン化を UX 改善として採用できる。
  - ログへの資格情報露出を避ける監査項目が必要。

## Architecture Pattern Evaluation

- Path based reverse proxy:
  - Description: 同一ホストで `/mlflow/` と `/streamlit/` を分割する。
  - Strengths: 同一オリジン、運用窓口一本化。
  - Risks: サブパス設定不備で表示崩れが起こる。
  - Notes: 採用。
- Host based reverse proxy:
  - Description: 別ホストでサービスを分離する。
  - Strengths: 設定が単純。
  - Risks: 再認証増加、証明書運用負荷。
  - Notes: 要件と不一致。
- Access gateway only:
  - Description: 外部 IdP 認証のみで統制する。
  - Strengths: 強いゼロトラスト統制。
  - Risks: 要件逸脱、導入コスト増加。
  - Notes: 将来候補。

## Design Decisions

### Decision: 同一ホスト配下のパス分割を採用

- **Context**: Streamlit から MLflow 遷移時の再認証を減らしたい。
- **Alternatives Considered**:
  1. 別ホスト名で公開する。
  2. 同一ホストのパス分割で公開する。
- **Selected Approach**:
  - Nginx が `/mlflow/` と `/streamlit/` を同一ホストで振り分ける。
- **Rationale**:
  - 要件変更と一致し、認証体験と運用管理を統一できる。
- **Trade-offs**:
  - サブパス設定は増えるが UX と運用面の利得が大きい。
- **Follow-up**:
  - Streamlit ベースパス、MLflow サブパス、WebSocket を統合試験で確認する。

### Decision: 二層認証モデルを維持

- **Context**: 入口防御を追加しつつ既存 Streamlit トークンを維持したい。
- **Alternatives Considered**:
  1. Basic 認証のみ。
  2. Streamlit トークンのみ。
  3. Basic 認証と Streamlit トークンの併用。
- **Selected Approach**:
  - Basic 認証を入口認証、トークンをアプリ内認可として併用する。
- **Rationale**:
  - 既存運用を壊さず段階防御を実現できる。
- **Trade-offs**:
  - 利用者向け説明が増える。
- **Follow-up**:
  - ドキュメントに認証レイヤ責務を明記する。

## Risks & Mitigations

- Streamlit WebSocket 切断リスク:
  - `Upgrade`/`Connection` 転送設定と回帰テストを必須化する。
- MLflow サブパス 404 リスク:
  - Nginx rewrite と API 疎通確認をセットで実施する。
- `htpasswd` 漏洩リスク:
  - `.gitignore` 管理外と権限最小化で運用する。
- 認証情報ログ露出リスク:
  - access/error ログの出力内容を監査する。

## References

- [NGINX auth basic module](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html)
- [NGINX basic authentication guide](https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-http-basic-authentication)
- [MLflow tracking server security](https://mlflow.org/docs/latest/ml/tracking/server/security/)
- [Streamlit reverse proxy discussion](https://discuss.streamlit.io/t/change-base-url-of-the-websocket/521)
