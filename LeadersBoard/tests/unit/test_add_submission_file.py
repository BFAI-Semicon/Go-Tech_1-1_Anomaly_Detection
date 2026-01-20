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

    def test_execute_updates_metadata_for_sequential_upload(self) -> None:
        """順次ファイルアップロードでメタデータが正しく更新されることを確認（要件1.1）"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage.add_file.return_value = {"filename": "data.py", "size": 512}

        use_case = AddSubmissionFile(mock_storage)

        file_obj = io.BytesIO(b"def process_data():\n    pass")

        # Act
        result = use_case.execute("sequential-submission", file_obj, "data.py", "user456")

        # Assert
        assert result == {"filename": "data.py", "size": 512}
        # add_fileが呼ばれ、メタデータが更新されることを確認
        mock_storage.add_file.assert_called_once_with("sequential-submission", file_obj, "data.py", "user456")

    def test_execute_allows_large_valid_files_for_sequential_upload(self) -> None:
        """順次アップロードで大きな有効サイズのファイルが許可されることを確認（要件1.3）"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage.add_file.return_value = {"filename": "large-dataset.zip", "size": 95 * 1024 * 1024}

        use_case = AddSubmissionFile(mock_storage)

        # 95MBのファイル（100MB制限未満）- 順次アップロードで有効
        large_but_valid_content = b"x" * (95 * 1024 * 1024)
        file_obj = io.BytesIO(large_but_valid_content)

        # Act
        result = use_case.execute("large-file-submission", file_obj, "large-dataset.zip", "user-large")

        # Assert - 大きなファイルでも制限内であれば許可される
        assert result["filename"] == "large-dataset.zip"
        assert result["size"] == 95 * 1024 * 1024
        mock_storage.add_file.assert_called_once()

    def test_execute_handles_concurrent_file_additions(self) -> None:
        """複数のファイルを順次追加する場合の処理が正しく動作することを確認"""
        # Arrange
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage.add_file.side_effect = [
            {"filename": "main.py", "size": 1024},
            {"filename": "config.yaml", "size": 256},
            {"filename": "data.zip", "size": 2048}
        ]

        use_case = AddSubmissionFile(mock_storage)

        # Act & Assert - 複数のファイルを順次追加
        files_to_add = [
            ("main.py", b"print('hello')", 1024),
            ("config.yaml", b"batch_size: 32", 256),
            ("data.zip", b"binary_data", 2048)
        ]

        for filename, content, expected_size in files_to_add:
            file_obj = io.BytesIO(content)
            result = use_case.execute("concurrent-submission", file_obj, filename, "user789")
            assert result["filename"] == filename
            assert result["size"] == expected_size

        # add_fileが各ファイルに対して呼ばれたことを確認
        assert mock_storage.add_file.call_count == 3
