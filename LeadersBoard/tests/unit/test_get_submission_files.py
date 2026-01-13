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
