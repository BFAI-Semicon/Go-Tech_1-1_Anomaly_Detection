from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any, cast

import requests

try:  # Streamlitは実行時にのみ必要。テストでは未インストールでも動作させる。
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover - テスト環境ではstreamlitが無いことを許容
    st = None  # type: ignore


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
    response = requests.post(url, headers=headers, files=[("files", f) for f in files], data=data, timeout=30)
    response.raise_for_status()
    return response.json()


def create_job(api_url: str, token: str, submission_id: str, config: dict[str, Any]) -> dict[str, Any]:
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


def fetch_job_logs(api_url: str, token: str, job_id: str) -> str:
    """GET /jobs/{job_id}/logs を取得する。"""
    url = api_url.rstrip("/") + f"/jobs/{job_id}/logs"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def add_job_to_state(state: dict[str, Any], job: dict[str, Any]) -> list[dict[str, Any]]:
    """セッションステートのジョブ一覧を先頭挿入し、重複は前方に寄せる。"""
    jobs: list[dict[str, Any]] = state.setdefault("jobs", [])
    job_id = job.get("job_id")
    if job_id:
        jobs = [j for j in jobs if j.get("job_id") != job_id]
    jobs.insert(0, job)
    state["jobs"] = jobs
    return jobs


def _render_submission_form(api_url: str, mlflow_url: str) -> None:
    if st is None:  # pragma: no cover
        raise RuntimeError("streamlit is not installed. Install it to run the UI.")

    st.header("Submission")
    token = st.text_input("API Token", type="password", key="token_input")
    uploaded_files = st.file_uploader("Upload files (main.py, config.yaml, etc.)", accept_multiple_files=True)
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


def _render_jobs(api_url: str, mlflow_url: str) -> None:
    if st is None:  # pragma: no cover
        return

    st.header("ジョブ一覧")
    token = st.session_state.get("token_input", "")
    jobs: list[dict[str, Any]] = st.session_state.get("jobs", [])
    if not jobs:
        st.info("まだジョブがありません。フォームから投稿してください。")
        return

    for job in list(jobs):
        job_id = cast(str | None, job.get("job_id"))
        submission_id = job.get("submission_id")
        col1, col2, col3 = st.columns([3, 3, 2])
        with col1:
            st.markdown(f"**Job ID:** {job_id}")
            st.caption(f"Submission: {submission_id}")
        with col2:
            status_data = None
            if token and job_id:
                try:
                    status_data = fetch_job_status(api_url, token, job_id)
                except Exception:  # pragma: no cover
                    status_data = None
            status_text = status_data.get("status") if status_data else job.get("status", "unknown")
            st.metric("Status", status_text)
            if status_data and status_data.get("run_id"):
                link = build_mlflow_run_link(mlflow_url, status_data["run_id"])
                st.markdown(f"[MLflow run]({link})")
        with col3:
            if st.button("Show logs", key=f"logs-{job_id or 'unknown'}"):
                if not token:
                    st.warning("API Tokenが必要です")
                elif not job_id:
                    st.warning("Job ID がありません")
                else:
                    try:
                        logs = fetch_job_logs(api_url, token, job_id)
                        st.code(logs, language="bash")
                    except Exception as exc:  # pragma: no cover
                        st.error(f"ログ取得に失敗しました: {exc}")


def main() -> None:  # pragma: no cover - UI起動時に実行
    if st is None:
        raise RuntimeError("streamlit is not installed. Install it to run the UI.")

    st.set_page_config(page_title="LeadersBoard", layout="wide")
    api_url = os.getenv("API_URL", "http://api:8010")
    mlflow_url = os.getenv("MLFLOW_URL", "http://mlflow:5010")

    _render_submission_form(api_url, mlflow_url)
    st.divider()
    _render_jobs(api_url, mlflow_url)


if __name__ == "__main__":  # pragma: no cover
    main()
