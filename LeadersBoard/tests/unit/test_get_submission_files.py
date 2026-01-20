from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.get_submission_files import GetSubmissionFiles


class TestGetSubmissionFiles:
    def test_execute_success(self) -> None:
        """正常にファイル一覧を取得できることを確認"""
        # Arrange
        mock_storage = MagicMock()
        expected_files = [
            {"filename": "main.py", "size": 2048, "uploaded_at": "2025-01-13T10:30:00"},
            {"filename": "config.yaml", "size": 512, "uploaded_at": "2025-01-13T10:30:15"},
        ]
        mock_storage.list_files.return_value = expected_files

        use_case = GetSubmissionFiles(mock_storage)

        # Act
        result = use_case.execute("test-submission", "user123")

        # Assert
        assert result == expected_files
        mock_storage.list_files.assert_called_once_with("test-submission", "user123")

    def test_execute_empty_files(self) -> None:
        """ファイルが存在しない場合空のリストが返されることを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.list_files.return_value = []

        use_case = GetSubmissionFiles(mock_storage)

        # Act
        result = use_case.execute("test-submission", "user123")

        # Assert
        assert result == []
        mock_storage.list_files.assert_called_once_with("test-submission", "user123")

    def test_execute_submission_not_exist(self) -> None:
        """存在しないsubmissionに対してエラーが発生することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.list_files.side_effect = ValueError("submission test-submission does not exist")

        use_case = GetSubmissionFiles(mock_storage)

        # Act & Assert
        with pytest.raises(ValueError, match="submission test-submission does not exist"):
            use_case.execute("test-submission", "user123")

    def test_execute_permission_denied(self) -> None:
        """権限のないユーザーに対してエラーが発生することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.list_files.side_effect = ValueError("user user123 does not own submission test-submission")

        use_case = GetSubmissionFiles(mock_storage)

        # Act & Assert
        with pytest.raises(ValueError, match="user user123 does not own submission test-submission"):
            use_case.execute("test-submission", "user123")

    def test_execute_with_metadata(self) -> None:
        """ファイルのメタデータ（サイズ・アップロード日時）が正しく返されることを確認"""
        # Arrange
        mock_storage = MagicMock()
        expected_files = [
            {
                "filename": "script.py",
                "size": 1024,
                "uploaded_at": "2025-01-13T12:00:00"
            },
            {
                "filename": "data.yaml",
                "size": 2048,
                "uploaded_at": "2025-01-13T12:05:00"
            },
        ]
        mock_storage.list_files.return_value = expected_files

        use_case = GetSubmissionFiles(mock_storage)

        # Act
        result = use_case.execute("test-submission", "user123")

        # Assert
        assert len(result) == 2
        assert result[0]["filename"] == "script.py"
        assert result[0]["size"] == 1024
        assert result[0]["uploaded_at"] == "2025-01-13T12:00:00"
        assert result[1]["filename"] == "data.yaml"
        assert result[1]["size"] == 2048
        assert result[1]["uploaded_at"] == "2025-01-13T12:05:00"
        mock_storage.list_files.assert_called_once_with("test-submission", "user123")

    def test_execute_lists_files_from_sequential_upload(self) -> None:
        """順次ファイルアップロードで追加されたファイルが正しく一覧表示されることを確認（要件8.1）"""
        # Arrange
        mock_storage = MagicMock()
        expected_files = [
            {"filename": "main.py", "size": 1024, "uploaded_at": "2025-01-13T10:00:00"},
            {"filename": "config.yaml", "size": 256, "uploaded_at": "2025-01-13T10:00:05"},
            {"filename": "data.py", "size": 2048, "uploaded_at": "2025-01-13T10:01:00"},  # 順次アップロードで追加
            {"filename": "model.zip", "size": 1048576, "uploaded_at": "2025-01-13T10:02:00"}  # 順次アップロードで追加
        ]
        mock_storage.list_files.return_value = expected_files

        use_case = GetSubmissionFiles(mock_storage)

        # Act
        result = use_case.execute("sequential-submission", "user456")

        # Assert
        assert len(result) == 4
        assert result == expected_files
        # 順次アップロードで追加されたファイルが含まれていることを確認
        filenames = {f["filename"] for f in result}
        assert "data.py" in filenames
        assert "model.zip" in filenames

    def test_execute_handles_empty_sequential_submission(self) -> None:
        """順次アップロード開始直後の空のsubmissionのファイル一覧取得を確認（要件8.1）"""
        # Arrange
        mock_storage = MagicMock()
        # 順次アップロード開始時は初期ファイルのみ
        initial_files = [
            {"filename": "main.py", "size": 512, "uploaded_at": "2025-01-13T09:00:00"}
        ]
        mock_storage.list_files.return_value = initial_files

        use_case = GetSubmissionFiles(mock_storage)

        # Act
        result = use_case.execute("empty-sequential-submission", "user999")

        # Assert
        assert len(result) == 1
        assert result[0]["filename"] == "main.py"
        assert result[0]["size"] == 512

    def test_execute_validates_user_ownership_for_sequential_files(self) -> None:
        """順次アップロードされたファイルに対する所有者権限チェックを確認（要件8.4）"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.list_files.side_effect = ValueError("user wrong_user does not own submission sequential-sub")

        use_case = GetSubmissionFiles(mock_storage)

        # Act & Assert
        with pytest.raises(ValueError, match="user wrong_user does not own submission sequential-sub"):
            use_case.execute("sequential-sub", "wrong_user")

        # 権限チェックが実行されたことを確認
        mock_storage.list_files.assert_called_once_with("sequential-sub", "wrong_user")
