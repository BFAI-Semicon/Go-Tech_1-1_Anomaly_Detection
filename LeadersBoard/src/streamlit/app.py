from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any, cast

import requests

try:  # Streamlitは実行時にのみ必要。テストでは未インストールでも動作させる。
    import streamlit as st  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - テスト環境ではstreamlitが無いことを許容
    st = None  # type: ignore[assignment]


def build_mlflow_run_link(mlflow_url: str, run_id: str) -> str:
    """MLflow UI の run リンクを生成する。"""
    base = mlflow_url.rstrip("/")
    return f"{base}/#/experiments/1/runs/{run_id}"


def submit_submission(
    api_url: str,
    token: str,
    files: Iterable[tuple[str, Any, str]],
    entrypoint: str = "main.py",
    config_file: str = "config.yaml",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST /submissions を呼び出して submission_id を取得する。"""
    url = api_url.rstrip("/") + "/submissions"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "entrypoint": entrypoint,
        "config_file": config_file,
        "metadata": json.dumps(metadata or {}),
    }
    response = requests.post(
        url, headers=headers, files=[("files", f) for f in files], data=data, timeout=30
    )
    response.raise_for_status()
    return response.json()


def create_job(
    api_url: str, token: str, submission_id: str, config: dict[str, Any]
) -> dict[str, Any]:
    """POST /jobs を呼び出して job_id を取得する。"""
    url = api_url.rstrip("/") + "/jobs"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"submission_id": submission_id, "config": config}
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_job_status(api_url: str, token: str, job_id: str) -> dict[str, Any] | None:
    """GET /jobs/{job_id}/status を取得する。"""
    url = api_url.rstrip("/") + f"/jobs/{job_id}/status"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def fetch_job_logs(api_url: str, token: str, job_id: str, tail_lines: int | None = None) -> str:
    """GET /jobs/{job_id}/logs を取得する。

    Args:
        api_url: API URL
        token: 認証トークン
        job_id: ジョブID
        tail_lines: 取得する最終行数（省略時は全行）
    """
    url = api_url.rstrip("/") + f"/jobs/{job_id}/logs"
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, int] = {}
    if tail_lines is not None:
        params["tail_lines"] = tail_lines
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    return data.get("logs", "")


def add_job_to_state(state: dict[str, Any], job: dict[str, Any]) -> list[dict[str, Any]]:
    """セッションステートのジョブ一覧を先頭挿入し、重複は前方に寄せる。"""
    jobs: list[dict[str, Any]] = state.setdefault("jobs", [])
    job_id = job.get("job_id")
    if job_id:
        jobs = [j for j in jobs if j.get("job_id") != job_id]
    jobs.insert(0, job)
    state["jobs"] = jobs
    return jobs


def has_running_jobs(jobs: list[dict[str, Any]]) -> bool:
    """実行中（pending/running）のジョブが存在するか確認する。"""
    return any(job.get("status") in ("pending", "running") for job in jobs)


def get_status_color(status: str) -> str:
    """ステータスに応じた絵文字を返す。"""
    if status == "completed":
        return "✅"
    elif status == "failed":
        return "❌"
    elif status in ("pending", "running"):
        return "⏳"
    else:
        return "❓"


def _render_submission_form(api_url: str, mlflow_url: str) -> None:
    if st is None:  # pragma: no cover
        raise RuntimeError("streamlit is not installed. Install it to run the UI.")

    st.header("Submission")
    token = st.text_input("API Token", type="password", key="token_input")
    uploaded_files = st.file_uploader(
        "Upload files (main.py, config.yaml, etc.)", accept_multiple_files=True
    )
    entrypoint = st.text_input("Entrypoint", value="main.py")
    config_file = st.text_input("Config file", value="config.yaml")
    metadata_text = st.text_area("metadata (JSON)", value='{"method":"padim"}')

    if st.button("Submit", type="primary"):
        if not token:
            st.error("API Tokenを入力してください。")
            return
        if not uploaded_files:
            st.error("少なくとも1つのファイルをアップロードしてください。")
            return
        try:
            metadata = json.loads(metadata_text) if metadata_text.strip() else {}
        except json.JSONDecodeError:
            st.error("metadata は JSON 形式で入力してください。")
            return

        files_payload = [(f.name, f, f.type or "application/octet-stream") for f in uploaded_files]
        try:
            submission = submit_submission(
                api_url=api_url,
                token=token,
                files=files_payload,
                entrypoint=entrypoint,
                config_file=config_file,
                metadata=metadata,
            )
            submission_id = submission["submission_id"]
            st.success(f"Submission created: {submission_id}")
        except Exception as exc:  # pragma: no cover - UI経由のみ
            st.error(f"Submission failed: {exc}")
            return

        # ジョブ投入
        try:
            job_resp = create_job(
                api_url=api_url,
                token=token,
                submission_id=submission_id,
                config={"resource_class": "medium"},
            )
            job_info = {
                "job_id": job_resp.get("job_id"),
                "submission_id": submission_id,
                "status": job_resp.get("status", "pending"),
                "mlflow_url": mlflow_url,
            }
            add_job_to_state(st.session_state, job_info)
            st.success(f"Job enqueued: {job_info['job_id']}")
        except Exception as exc:  # pragma: no cover
            st.error(f"Job enqueue failed: {exc}")


def _render_job_logs(
    api_url: str,
    token: str,
    job_id: str,
    is_running: bool,
) -> None:
    """ジョブのログを表示する。

    Args:
        api_url: API URL
        token: 認証トークン
        job_id: ジョブID
        is_running: 実行中かどうか
    """
    if st is None:  # pragma: no cover
        return

    if not token:
        st.warning("API Tokenが必要です")
        return

    # 実行中のジョブは最新100行のみ取得（パフォーマンス最適化）
    tail_lines = 100 if is_running else None

    try:
        logs = fetch_job_logs(api_url, token, job_id, tail_lines=tail_lines)
        if logs:
            st.code(logs, language="log", line_numbers=True)
            if is_running and tail_lines:
                st.caption(f"最新 {tail_lines} 行を表示中（リアルタイム更新）")
        else:
            st.info("ログはまだ出力されていません。")
    except Exception as exc:  # pragma: no cover
        st.error(f"ログ取得に失敗しました: {exc}")


def _render_jobs(api_url: str, mlflow_url: str) -> None:
    if st is None:  # pragma: no cover
        return

    # ヘッダーと手動更新ボタン
    header_col, refresh_col = st.columns([6, 1])
    with header_col:
        st.header("ジョブ一覧")
    with refresh_col:
        if st.button("🔄", help="手動更新"):
            st.rerun()

    token = st.session_state.get("token_input", "")
    jobs: list[dict[str, Any]] = st.session_state.get("jobs", [])
    if not jobs:
        st.info("まだジョブがありません。フォームから投稿してください。")
        return

    # 実行中ジョブの検出用（最初にセッションステートから判定）
    has_pending_or_running = any(job.get("status") in ("pending", "running") for job in jobs)

    # 実行中ジョブがない場合は、APIリクエストをスキップしてキャッシュデータのみ使用
    fetch_status = has_pending_or_running
    running_jobs_detected = False

    for job in list(jobs):
        job_id = cast(str | None, job.get("job_id"))
        submission_id = job.get("submission_id")

        # ジョブカードの表示
        with st.container():
            col1, col2 = st.columns([3, 5])
            with col1:
                st.markdown(f"**Job ID:** `{job_id}`")
                st.caption(f"Submission: {submission_id}")

            with col2:
                status_data = None
                # 実行中ジョブがある場合のみAPIからステータスを取得（パフォーマンス最適化）
                if fetch_status and token and job_id:
                    try:
                        status_data = fetch_job_status(api_url, token, job_id)
                    except Exception:  # pragma: no cover
                        status_data = None
                status_text = str(
                    status_data.get("status") if status_data else job.get("status", "unknown")
                )

                # セッションステートを更新
                job["status"] = status_text

                # 実行中ジョブの検出
                if status_text in ("pending", "running"):
                    running_jobs_detected = True

                # ステータス表示（色分け）
                emoji = get_status_color(status_text)
                st.markdown(f"{emoji} **{status_text}**")

                if status_data and status_data.get("run_id"):
                    link = build_mlflow_run_link(mlflow_url, status_data["run_id"])
                    st.markdown(f"[MLflow run]({link})")

            # ログ表示エリア
            if job_id:
                is_running = status_text == "running"
                is_completed = status_text in ("completed", "failed")

                if is_running:
                    # 実行中ジョブはリアルタイムログを表示
                    with st.expander("📋 実行中のログ", expanded=True):
                        _render_job_logs(api_url, token, job_id, is_running=True)
                elif is_completed:
                    # 完了/失敗ジョブは折りたたみでログを表示
                    with st.expander("📋 ログを表示", expanded=False):
                        _render_job_logs(api_url, token, job_id, is_running=False)

            st.divider()

    # 自動更新の状態表示
    if running_jobs_detected:
        st.caption("⏳ 実行中のジョブがあります。5秒ごとに自動更新されます。")
    elif jobs:
        # 全ジョブが終了している場合
        st.caption(
            "✅ 全てのジョブが終了しました。新しいジョブを投稿すると自動更新が再開されます。"
        )


def main() -> None:  # pragma: no cover - UI起動時に実行
    if st is None:
        raise RuntimeError("streamlit is not installed. Install it to run the UI.")

    st.set_page_config(page_title="LeadersBoard", layout="wide")
    api_url = os.getenv("API_URL", "http://api:8010")
    mlflow_url = os.getenv("MLFLOW_URL", "http://mlflow:5010")

    _render_submission_form(api_url, mlflow_url)
    st.divider()

    # Fragment自動更新を適用（ただし実行中ジョブがない場合はAPIリクエストをスキップ）
    render_jobs_with_auto_refresh = st.fragment(run_every="5s")(_render_jobs)
    render_jobs_with_auto_refresh(api_url, mlflow_url)


if __name__ == "__main__":  # pragma: no cover
    main()
