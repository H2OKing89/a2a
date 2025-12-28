"""Tests for security utilities."""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from src.utils.security import (
    INSECURE_BITS,
    SECURE_DIR_MODE,
    SECURE_FILE_MODE,
    check_file_permissions,
    ensure_secure_directory,
    fix_file_permissions,
    get_permission_string,
    is_file_secure,
    secure_file_create,
)


class TestCheckFilePermissions:
    """Tests for check_file_permissions function."""

    def test_nonexistent_file_returns_true(self, tmp_path: Path) -> None:
        """Non-existent files should return True (no issues)."""
        fake_file = tmp_path / "nonexistent.txt"
        assert check_file_permissions(fake_file) is True

    def test_secure_file_returns_true(self, tmp_path: Path) -> None:
        """Files with 600 permissions should return True."""
        secure_file = tmp_path / "secure.txt"
        secure_file.write_text("secret")
        os.chmod(secure_file, 0o600)
        assert check_file_permissions(secure_file, warn=False) is True

    def test_insecure_file_returns_false(self, tmp_path: Path) -> None:
        """Files with world-readable permissions should return False."""
        insecure_file = tmp_path / "insecure.txt"
        insecure_file.write_text("secret")
        os.chmod(insecure_file, 0o644)
        assert check_file_permissions(insecure_file, warn=False) is False

    def test_fix_parameter_fixes_permissions(self, tmp_path: Path) -> None:
        """When fix=True, insecure permissions should be fixed."""
        insecure_file = tmp_path / "fixme.txt"
        insecure_file.write_text("secret")
        os.chmod(insecure_file, 0o644)

        result = check_file_permissions(insecure_file, fix=True, warn=False)
        assert result is True
        assert stat.S_IMODE(insecure_file.stat().st_mode) == SECURE_FILE_MODE


class TestFixFilePermissions:
    """Tests for fix_file_permissions function."""

    def test_fix_to_600(self, tmp_path: Path) -> None:
        """Should change permissions to 600."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        os.chmod(test_file, 0o644)

        result = fix_file_permissions(test_file)
        assert result is True
        assert stat.S_IMODE(test_file.stat().st_mode) == 0o600

    def test_fix_nonexistent_returns_false(self, tmp_path: Path) -> None:
        """Non-existent files should return False."""
        fake_file = tmp_path / "nonexistent.txt"
        assert fix_file_permissions(fake_file) is False

    def test_fix_with_custom_mode(self, tmp_path: Path) -> None:
        """Should support custom permission modes."""
        test_file = tmp_path / "custom.txt"
        test_file.write_text("content")

        result = fix_file_permissions(test_file, mode=0o400)
        assert result is True
        assert stat.S_IMODE(test_file.stat().st_mode) == 0o400


class TestSecureFileCreate:
    """Tests for secure_file_create function."""

    def test_creates_file_with_secure_permissions(self, tmp_path: Path) -> None:
        """File should be created with 600 permissions."""
        secure_path = tmp_path / "secure_new.txt"
        result = secure_file_create(secure_path, "secret content")

        assert result is True
        assert secure_path.exists()
        assert secure_path.read_text() == "secret content"
        assert stat.S_IMODE(secure_path.stat().st_mode) == SECURE_FILE_MODE

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if they don't exist."""
        nested_path = tmp_path / "deep" / "nested" / "file.txt"
        result = secure_file_create(nested_path, "content")

        assert result is True
        assert nested_path.exists()

    def test_handles_bytes_content(self, tmp_path: Path) -> None:
        """Should handle bytes content."""
        binary_path = tmp_path / "binary.bin"
        content = b"\x00\x01\x02\x03"
        result = secure_file_create(binary_path, content)

        assert result is True
        assert binary_path.read_bytes() == content


class TestIsFileSecure:
    """Tests for is_file_secure function."""

    def test_secure_file(self, tmp_path: Path) -> None:
        """Secure file should return True."""
        secure_file = tmp_path / "secure.txt"
        secure_file.write_text("secret")
        os.chmod(secure_file, 0o600)
        assert is_file_secure(secure_file) is True

    def test_insecure_file(self, tmp_path: Path) -> None:
        """Insecure file should return False."""
        insecure_file = tmp_path / "insecure.txt"
        insecure_file.write_text("secret")
        os.chmod(insecure_file, 0o644)
        assert is_file_secure(insecure_file) is False

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Non-existent file should return True."""
        fake_file = tmp_path / "nonexistent.txt"
        assert is_file_secure(fake_file) is True


class TestGetPermissionString:
    """Tests for get_permission_string function."""

    def test_600_permissions(self, tmp_path: Path) -> None:
        """600 should return 'rw-------'."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        os.chmod(test_file, 0o600)
        assert get_permission_string(test_file) == "rw-------"

    def test_644_permissions(self, tmp_path: Path) -> None:
        """644 should return 'rw-r--r--'."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        os.chmod(test_file, 0o644)
        assert get_permission_string(test_file) == "rw-r--r--"

    def test_755_permissions(self, tmp_path: Path) -> None:
        """755 should return 'rwxr-xr-x'."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        os.chmod(test_file, 0o755)
        assert get_permission_string(test_file) == "rwxr-xr-x"

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Non-existent file should return 'not found'."""
        fake_file = tmp_path / "nonexistent.txt"
        assert get_permission_string(fake_file) == "not found"


class TestEnsureSecureDirectory:
    """Tests for ensure_secure_directory function."""

    def test_creates_new_directory(self, tmp_path: Path) -> None:
        """Should create directory with secure permissions."""
        new_dir = tmp_path / "secure_dir"
        result = ensure_secure_directory(new_dir)

        assert result is True
        assert new_dir.exists()
        assert new_dir.is_dir()
        assert stat.S_IMODE(new_dir.stat().st_mode) == SECURE_DIR_MODE

    def test_fixes_existing_insecure_directory(self, tmp_path: Path) -> None:
        """Should fix permissions on existing insecure directory."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir(mode=0o755)

        result = ensure_secure_directory(existing_dir)
        assert result is True
        assert stat.S_IMODE(existing_dir.stat().st_mode) == SECURE_DIR_MODE

    def test_fails_on_file_path(self, tmp_path: Path) -> None:
        """Should fail if path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        result = ensure_secure_directory(file_path)
        assert result is False
