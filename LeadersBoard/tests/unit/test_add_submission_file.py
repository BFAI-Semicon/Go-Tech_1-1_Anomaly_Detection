from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest

from src.domain.add_submission_file import AddSubmissionFile


class TestAddSubmissionFile:
    def test_execute_success(self) -> None:
        """正常にファイルを追加できることを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage.add_file.return_value = {"filename": "test.py", "size": 100}

        use_case = AddSubmissionFile(mock_storage)

        file_content = b"print('hello')"
        file_obj = io.BytesIO(file_content)

        # Act
        result = use_case.execute("test-submission", file_obj, "test.py", "user123")

        # Assert
        assert result == {"filename": "test.py", "size": 100}
        mock_storage.exists.assert_called_once_with("test-submission")
        mock_storage.add_file.assert_called_once_with("test-submission", file_obj, "test.py", "user123")

    def test_execute_submission_not_exist(self) -> None:
        """存在しないsubmissionに対してエラーが発生することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = False

        use_case = AddSubmissionFile(mock_storage)

        file_obj = io.BytesIO(b"content")

        # Act & Assert
        with pytest.raises(ValueError, match="submission test-submission does not exist"):
            use_case.execute("test-submission", file_obj, "test.py", "user123")

    def test_execute_file_too_large(self) -> None:
        """ファイルサイズが上限を超える場合エラーが発生することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True

        use_case = AddSubmissionFile(mock_storage)

        # 100MB + 1 byte のファイルを作成
        large_content = b"x" * (100 * 1024 * 1024 + 1)
        file_obj = io.BytesIO(large_content)

        # Act & Assert
        with pytest.raises(ValueError, match="file size .* exceeds maximum"):
            use_case.execute("test-submission", file_obj, "test.py", "user123")

    def test_execute_invalid_extension(self) -> None:
        """許可されていない拡張子のファイルに対してエラーが発生することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True

        use_case = AddSubmissionFile(mock_storage)

        file_obj = io.BytesIO(b"content")

        # Act & Assert
        with pytest.raises(ValueError, match="file extension not allowed"):
            use_case.execute("test-submission", file_obj, "test.exe", "user123")

    def test_execute_path_traversal(self) -> None:
        """パストラバーサル攻撃に対してエラーが発生することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True

        use_case = AddSubmissionFile(mock_storage)

        file_obj = io.BytesIO(b"content")

        # Act & Assert
        with pytest.raises(ValueError, match="invalid filename"):
            use_case.execute("test-submission", file_obj, "../test.py", "user123")

        with pytest.raises(ValueError, match="invalid filename"):
            use_case.execute("test-submission", file_obj, "path/test.py", "user123")

    @pytest.mark.parametrize("filename", ["test.py", "config.yaml", "data.zip", "archive.tar.gz"])
    def test_execute_valid_extensions(self, filename: str) -> None:
        """許可された拡張子のファイルが受け入れられることを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage.add_file.return_value = {"filename": filename, "size": 100}

        use_case = AddSubmissionFile(mock_storage)

        file_obj = io.BytesIO(b"content")

        # Act
        result = use_case.execute("test-submission", file_obj, filename, "user123")

        # Assert
        assert result["filename"] == filename
        mock_storage.add_file.assert_called_once_with("test-submission", file_obj, filename, "user123")
