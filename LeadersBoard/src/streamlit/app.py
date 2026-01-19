from __future__ import annotations

import json
import os
import time
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


def add_submission_file(
    api_url: str,
    token: str,
    submission_id: str,
    file: Any,
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    submissionにファイルを1つ追加する（リトライ付き）。

    Args:
        api_url: API URL
        token: 認証トークン
        submission_id: submission ID
        file: アップロードするファイル
        max_retries: 最大リトライ回数

    Returns:
        {"filename": str, "size": int}

    Raises:
        requests.HTTPError: 4xxエラー（リトライなし）
        Exception: リトライ3回失敗後
    """
    url = f"{api_url.rstrip('/')}/submissions/{submission_id}/files"
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(max_retries):
        file.seek(0)  # Reset file pointer to beginning for retry
        try:
            files_payload = {"file": (file.name, file, file.type)}
            response = requests.post(url, headers=headers, files=files_payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            if 400 <= exc.response.status_code < 500:
                # 4xxエラー: リトライしない
                raise
            if attempt < max_retries - 1:
                # 5xxエラー: リトライ
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise Exception("Max retries exceeded") from exc
        except Exception as exc:
            if attempt < max_retries - 1:
                # その他のエラー: リトライ
                time.sleep(2 ** attempt)
                continue
            raise Exception("Max retries exceeded") from exc

    raise Exception("Max retries exceeded")


def submit_files_sequentially(
    api_url: str,
    token: str,
    files: list[Any],
    entrypoint: str,
    config_file: str,
    metadata: dict[str, Any],
) -> str:
    """
    ファイルを順次アップロードする。

    Args:
        api_url: API URL
        token: 認証トークン
        files: アップロードするファイルリスト
        entrypoint: エントリポイントファイル名
        config_file: 設定ファイル名
        metadata: メタデータ

    Returns:
        submission_id: 作成されたsubmission ID

    Raises:
        Exception: アップロード失敗
    """
    if not files:
        raise ValueError("No files to upload")

    # Streamlit UI要素（テスト時はNone）
    progress_placeholder = None
    if st is not None:
        progress_placeholder = st.empty()

    # 最初のファイルでsubmission作成
    first_file = files[0]
    files_payload = [(first_file.name, first_file, first_file.type or "application/octet-stream")]
    submission = submit_submission(
        api_url=api_url,
        token=token,
        files=files_payload,
        entrypoint=entrypoint,
        config_file=config_file,
        metadata=metadata,
    )
    submission_id = submission["submission_id"]

    # 進捗表示
    if progress_placeholder is not None:
        progress_placeholder.info(f"1/{len(files)} ファイルをアップロード中...")

    # 2番目以降のファイルを順次アップロード
    for i, file in enumerate(files[1:], start=2):
        try:
            if progress_placeholder is not None:
                progress_placeholder.info(f"{i}/{len(files)} ファイルをアップロード中...")
            add_submission_file(api_url, token, submission_id, file)
        except Exception as exc:
            error_msg = f"ファイルアップロード失敗: {file.name} - {exc}"
            if progress_placeholder is not None:
                progress_placeholder.error(error_msg)
            raise Exception(error_msg) from exc

    # 完了メッセージ
    if progress_placeholder is not None:
        progress_placeholder.success(f"全ファイル（{len(files)}件）のアップロードが完了しました。")

    return submission_id


def _render_submission_form(api_url: str, mlflow_url: str) -> None:
    if st is None:  # pragma: no cover
        raise RuntimeError("streamlit is not installed. Install it to run the UI.")

    st.header("Submission")
    token = st.text_input("API Token", type="password", key="token_input")
    uploaded_files = st.file_uploader("Upload files (main.py, config.yaml, etc.)", accept_multiple_files=True)
    entrypoint = st.text_input("Entrypoint", value="main.py")
    config_file = st.text_input("Config file", value="config.yaml")
    metadata_text = st.text_area("metadata (JSON)", value='{"method":"padim"}')

    # アップロード完了状態の取得
    upload_complete = st.session_state.get("upload_complete", False)
    submission_id = st.session_state.get("submission_id")

    # Submitボタン（アップロード処理）
    submit_disabled = st.session_state.get("uploading", False)
    if st.button("Submit", type="primary", disabled=submit_disabled):
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

        # アップロード開始
        st.session_state["uploading"] = True
        st.session_state["upload_complete"] = False

        try:
            # 順次アップロード実行
            submission_id = submit_files_sequentially(
                api_url=api_url,
                token=token,
                files=uploaded_files,
                entrypoint=entrypoint,
                config_file=config_file,
                metadata=metadata,
            )
            st.session_state["submission_id"] = submission_id
            st.session_state["upload_complete"] = True
            st.success(f"Submission created: {submission_id}")
            st.rerun()  # UI更新
        except Exception as exc:  # pragma: no cover - UI経由のみ
            st.error(f"Submission failed: {exc}")
        finally:
            st.session_state["uploading"] = False

    # ジョブ投入ボタン（アップロード完了後に有効化）
    if upload_complete and submission_id:
        if st.button("Enqueue Job", type="secondary"):
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
                # ジョブ投入後に状態をリセット
                st.session_state["upload_complete"] = False
                st.session_state["submission_id"] = None
            except Exception as exc:  # pragma: no cover
                st.error(f"Job enqueue failed: {exc}")

    # アップロード中の状態表示
    if st.session_state.get("uploading"):
        st.info("ファイルアップロード中...")

    # アップロード完了の状態表示
    if upload_complete:
        st.success("全ファイルのアップロードが完了しました。ジョブを投入してください。")


def _render_jobs(api_url: str, mlflow_url: str) -> None:
    if st is None:  # pragma: no cover
        return

    st.header("ジョブ一覧")
    token = st.session_state.get("token_input", "")
    jobs: list[dict[str, Any]] = st.session_state.get("jobs", [])
    if not jobs:
        st.info("まだジョブがありません。フォームから投稿してください。")
        return

    # 実行中ジョブの検出用（最初にセッションステートから判定）
    has_pending_or_running = any(
        job.get("status") in ("pending", "running") for job in jobs
    )

    # 実行中ジョブがない場合は、APIリクエストをスキップしてキャッシュデータのみ使用
    fetch_status = has_pending_or_running
    running_jobs_detected = False

    for job in list(jobs):
        job_id = cast(str | None, job.get("job_id"))
        submission_id = job.get("submission_id")
        col1, col2, col3 = st.columns([3, 3, 2])
        with col1:
            st.markdown(f"**Job ID:** {job_id}")
            st.caption(f"Submission: {submission_id}")
        with col2:
            status_data = None
            # 実行中ジョブがある場合のみAPIからステータスを取得（パフォーマンス最適化）
            if fetch_status and token and job_id:
                try:
                    status_data = fetch_job_status(api_url, token, job_id)
                except Exception:  # pragma: no cover
                    status_data = None
            status_text = str(status_data.get("status") if status_data else job.get("status", "unknown"))

            # 実行中ジョブの検出
            if status_text in ("pending", "running"):
                running_jobs_detected = True

            # ステータス表示（色分け）
            emoji = get_status_color(status_text)
            st.markdown(f"{emoji} **{status_text}**")

            if status_data and status_data.get("run_id"):
                link = build_mlflow_run_link(mlflow_url, status_data["run_id"])
                st.markdown(f"[MLflow run]({link})")
        with col3:
            # 実行中またはpendingの場合は状態を表示
            if status_text in ("pending", "running"):
                st.caption(f"⏳ {status_text}...")
            elif status_text in ("completed", "failed"):
                # ジョブが終了している場合、expanderでログを表示（自動更新で閉じない）
                with st.expander("📋 View Logs", expanded=False):
                    if not token:
                        st.warning("API Tokenが必要です")
                    elif not job_id:
                        st.warning("Job ID がありません")
                    else:
                        try:
                            logs = fetch_job_logs(api_url, token, job_id)
                            st.text_area(
                                "Job Logs",
                                logs,
                                height=400,
                                key=f"logs-content-{job_id}",
                                label_visibility="collapsed"
                            )
                        except Exception as exc:  # pragma: no cover
                            st.error(f"ログ取得に失敗しました: {exc}")
            else:
                st.caption(f"Status: {status_text}")

    # 自動更新の状態表示
    if running_jobs_detected:
        st.caption("⏳ 実行中のジョブがあります。5秒ごとに自動更新されます。")
    elif jobs:
        # 全ジョブが終了している場合
        st.caption("✅ 全てのジョブが終了しました。新しいジョブを投稿すると自動更新が再開されます。")


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
