from __future__ import annotations

import io
import json
import textwrap

from src.ports.job_status_port import JobStatus

AUTH_HEADER = {"Authorization": "Bearer integration-token"}


def _runner_script(run_id: str) -> str:
    return textwrap.dedent(
        """\
        import argparse
        import json
        import os

        def main():
            parser = argparse.ArgumentParser()
            parser.add_argument("--config", required=True)
            parser.add_argument("--output", required=True)
            args = parser.parse_args()
            os.makedirs(args.output, exist_ok=True)
            result_path = os.path.join(args.output, "result.txt")
            with open(result_path, "w") as out_file:
                out_file.write("completed")
            metrics_path = os.path.join(args.output, "metrics.json")
            with open(metrics_path, "w") as metrics_file:
                json.dump({"params": {"method": "test"}, "metrics": {"auc": 0.95}}, metrics_file)

        if __name__ == "__main__":
            main()
        """
    )


def _buffer_from_text(content: str, name: str) -> io.BytesIO:
    buffer = io.BytesIO(content.encode())
    buffer.name = name
    return buffer


def _post_bulk_submission(
    client,
    script: str,
    config: str = "batch_size: 1",
    entrypoint: str = "main.py",
    config_file: str = "config.yaml",
) -> tuple[str, int]:
    """一括アップロードでのsubmission作成（既存方式）"""
    files = [
        (
            "files",
            (
                entrypoint,
                _buffer_from_text(script, entrypoint),
                "text/x-python",
            ),
        ),
        (
            "files",
            (
                config_file,
                _buffer_from_text(config, config_file),
                "text/x-yaml",
            ),
        ),
    ]
    payload = {"metadata": json.dumps({"entrypoint": entrypoint, "config_file": config_file})}
    response = client.post(
        "/submissions",
        headers=AUTH_HEADER,
        files=files,
        data=payload,
    )
    return response.json().get("submission_id"), response.status_code


def _post_sequential_submission(
    client,
    script: str,
    config: str = "batch_size: 1",
    entrypoint: str = "main.py",
    config_file: str = "config.yaml",
) -> tuple[str, int]:
    """順次アップロードでのsubmission作成（新方式）"""
    # 最初のファイルでsubmission作成
    files = [
        (
            "files",
            (
                entrypoint,
                _buffer_from_text(script, entrypoint),
                "text/x-python",
            ),
        ),
    ]
    payload = {"metadata": json.dumps({"entrypoint": entrypoint, "config_file": config_file})}
    response = client.post(
        "/submissions",
        headers=AUTH_HEADER,
        files=files,
        data=payload,
    )
    submission_id = response.json().get("submission_id")

    # 2番目のファイルを追加
    config_file_buffer = _buffer_from_text(config, config_file)
    add_response = client.post(
        f"/submissions/{submission_id}/files",
        headers=AUTH_HEADER,
        files={"file": (config_file, config_file_buffer, "text/x-yaml")},
    )
    assert add_response.status_code == 201

    return submission_id, response.status_code


class TestBackwardCompatibility:
    """後方互換性テストスイート"""

    def test_bulk_upload_still_works(self, integration_context) -> None:
        """既存の一括アップロード機能が引き続き動作することを確認"""
        client = integration_context.client

        # 一括アップロードでsubmission作成
        submission_id, status_code = _post_bulk_submission(client, _runner_script("bulk-test"))
        assert status_code == 201
        assert submission_id

        # ファイル一覧を確認
        files_response = client.get(f"/submissions/{submission_id}/files", headers=AUTH_HEADER)
        assert files_response.status_code == 200
        files = files_response.json()["files"]
        assert len(files) == 2

        filenames = {f["filename"] for f in files}
        assert filenames == {"main.py", "config.yaml"}

        # ジョブ投入が可能
        job_response = client.post(
            "/jobs",
            headers=AUTH_HEADER,
            json={"submission_id": submission_id, "config": {"lr": 0.01}},
        )
        assert job_response.status_code == 202

    def test_sequential_upload_works(self, integration_context) -> None:
        """新しい順次アップロード機能が動作することを確認"""
        client = integration_context.client

        # 順次アップロードでsubmission作成
        submission_id, status_code = _post_sequential_submission(client, _runner_script("sequential-test"))
        assert status_code == 201
        assert submission_id

        # ファイル一覧を確認
        files_response = client.get(f"/submissions/{submission_id}/files", headers=AUTH_HEADER)
        assert files_response.status_code == 200
        files = files_response.json()["files"]
        assert len(files) == 2

        filenames = {f["filename"] for f in files}
        assert filenames == {"main.py", "config.yaml"}

        # ジョブ投入が可能
        job_response = client.post(
            "/jobs",
            headers=AUTH_HEADER,
            json={"submission_id": submission_id, "config": {"lr": 0.01}},
        )
        assert job_response.status_code == 202

    def test_both_methods_produce_same_metadata_format(self, integration_context) -> None:
        """一括アップロードと順次アップロードで同じメタデータ形式が生成されることを確認"""
        client = integration_context.client

        # 一括アップロード
        bulk_submission_id, _ = _post_bulk_submission(client, _runner_script("bulk-meta"))

        # 順次アップロード
        sequential_submission_id, _ = _post_sequential_submission(client, _runner_script("sequential-meta"))

        # 両方のメタデータを比較
        bulk_metadata = integration_context.storage.load_metadata(bulk_submission_id)
        sequential_metadata = integration_context.storage.load_metadata(sequential_submission_id)

        # 必須フィールドが同じであることを確認
        required_fields = ["user_id", "entrypoint", "config_file", "files"]
        for field in required_fields:
            assert field in bulk_metadata
            assert field in sequential_metadata

        # entrypointとconfig_fileが同じ
        assert bulk_metadata["entrypoint"] == sequential_metadata["entrypoint"] == "main.py"
        assert bulk_metadata["config_file"] == sequential_metadata["config_file"] == "config.yaml"

        # filesリストが同じ内容
        assert set(bulk_metadata["files"]) == set(sequential_metadata["files"])
        assert set(bulk_metadata["files"]) == {"main.py", "config.yaml"}

    def test_both_methods_can_be_processed_identically_by_jobs(self, integration_context) -> None:
        """一括アップロードと順次アップロードで作成されたsubmissionが同じようにジョブ処理されることを確認"""
        client = integration_context.client

        # 一括アップロードのsubmission作成
        bulk_submission_id, _ = _post_bulk_submission(client, _runner_script("bulk-job"))

        # 順次アップロードのsubmission作成
        sequential_submission_id, _ = _post_sequential_submission(client, _runner_script("sequential-job"))

        # 両方でジョブ投入
        bulk_job_response = client.post(
            "/jobs",
            headers=AUTH_HEADER,
            json={"submission_id": bulk_submission_id, "config": {"lr": 0.01}},
        )
        assert bulk_job_response.status_code == 202
        bulk_job_id = bulk_job_response.json()["job_id"]

        sequential_job_response = client.post(
            "/jobs",
            headers=AUTH_HEADER,
            json={"submission_id": sequential_submission_id, "config": {"lr": 0.01}},
        )
        assert sequential_job_response.status_code == 202
        sequential_job_id = sequential_job_response.json()["job_id"]

        # 両方のジョブを実行
        bulk_payload = integration_context.queue_adapter.dequeue()
        assert bulk_payload
        integration_context.job_worker.execute_job(bulk_payload)

        sequential_payload = integration_context.queue_adapter.dequeue()
        assert sequential_payload
        integration_context.job_worker.execute_job(sequential_payload)

        # 両方のジョブが正常完了することを確認
        bulk_status = integration_context.status_adapter.get_status(bulk_job_id)
        sequential_status = integration_context.status_adapter.get_status(sequential_job_id)

        assert bulk_status["status"] == JobStatus.COMPLETED.value
        assert sequential_status["status"] == JobStatus.COMPLETED.value

        assert bulk_status["run_id"] == "mock-run-id"
        assert sequential_status["run_id"] == "mock-run-id"

    def test_parallel_operation_of_new_and_existing_features(self, integration_context) -> None:
        """新機能と既存機能が並行して動作することを確認"""
        client = integration_context.client

        # 同時に複数のsubmissionを作成（一括と順次を混在）
        submissions = []

        # 一括アップロード × 2
        for i in range(2):
            submission_id, status_code = _post_bulk_submission(
                client, _runner_script(f"bulk-parallel-{i}")
            )
            assert status_code == 201
            submissions.append(("bulk", submission_id))

        # 順次アップロード × 2
        for i in range(2):
            submission_id, status_code = _post_sequential_submission(
                client, _runner_script(f"sequential-parallel-{i}")
            )
            assert status_code == 201
            submissions.append(("sequential", submission_id))

        # 全submissionのファイル一覧を確認
        for _method, submission_id in submissions:
            files_response = client.get(f"/submissions/{submission_id}/files", headers=AUTH_HEADER)
            assert files_response.status_code == 200
            files = files_response.json()["files"]
            assert len(files) == 2
            filenames = {f["filename"] for f in files}
            assert filenames == {"main.py", "config.yaml"}

        # 全submissionでジョブ投入
        job_ids = []
        for _method, submission_id in submissions:
            job_response = client.post(
                "/jobs",
                headers=AUTH_HEADER,
                json={"submission_id": submission_id, "config": {"lr": 0.01}},
            )
            assert job_response.status_code == 202
            job_ids.append(job_response.json()["job_id"])

        # 全ジョブを実行
        for job_id in job_ids:
            payload = integration_context.queue_adapter.dequeue()
            assert payload
            integration_context.job_worker.execute_job(payload)

            status = integration_context.status_adapter.get_status(job_id)
            assert status["status"] == JobStatus.COMPLETED.value
            assert status["run_id"] == "mock-run-id"

    def test_mixed_submission_creation_methods_maintain_consistency(self, integration_context) -> None:
        """一括と順次が混在しても全体として矛盾がないことを確認"""
        client = integration_context.client

        # 異なる方法でsubmissionを作成
        bulk_id, _ = _post_bulk_submission(client, _runner_script("bulk-mixed"))
        sequential_id, _ = _post_sequential_submission(client, _runner_script("sequential-mixed"))

        # 両方のsubmissionが同じ構造を持つことを確認
        for submission_id in [bulk_id, sequential_id]:
            # ストレージから直接確認
            assert integration_context.storage.exists(submission_id)

            metadata = integration_context.storage.load_metadata(submission_id)
            assert "files" in metadata
            assert len(metadata["files"]) == 2
            assert "main.py" in metadata["files"]
            assert "config.yaml" in metadata["files"]

            # API経由でも確認
            files_response = client.get(f"/submissions/{submission_id}/files", headers=AUTH_HEADER)
            assert files_response.status_code == 200
            files = files_response.json()["files"]
            assert len(files) == 2

        # 両方のsubmissionがジョブシステムで同じように扱われることを確認
        for submission_id in [bulk_id, sequential_id]:
            job_response = client.post(
                "/jobs",
                headers=AUTH_HEADER,
                json={"submission_id": submission_id, "config": {"lr": 0.01}},
            )
            assert job_response.status_code == 202
