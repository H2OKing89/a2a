"""
Tests for Audible auth file encryption functionality.

Tests the encryption module without requiring real Audible credentials.
Uses monkeypatching to mock the upstream audible library calls.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audible.encryption import (
    AuthFileEncryption,
    get_auth_password_from_env,
    get_encryption_config,
    get_file_encryption_style,
    is_file_encrypted,
    load_auth,
    save_auth,
)


class TestAuthFileEncryption:
    """Tests for AuthFileEncryption dataclass."""

    def test_default_values(self):
        """Test default encryption config values."""
        enc = AuthFileEncryption()
        assert enc.password is None
        assert enc.encryption == "json"
        assert enc.kdf_iterations == 50_000

    def test_custom_values(self):
        """Test custom encryption config values."""
        enc = AuthFileEncryption(
            password="secret123",
            encryption="bytes",
            kdf_iterations=10_000,
        )
        assert enc.password == "secret123"
        assert enc.encryption == "bytes"
        assert enc.kdf_iterations == 10_000

    def test_kdf_iterations_validation_too_low(self):
        """Test that kdf_iterations must be >= 1."""
        with pytest.raises(ValueError, match="kdf_iterations must be between 1 and 65535"):
            AuthFileEncryption(kdf_iterations=0)

    def test_kdf_iterations_validation_too_high(self):
        """Test that kdf_iterations must be <= 65535."""
        with pytest.raises(ValueError, match="kdf_iterations must be between 1 and 65535"):
            AuthFileEncryption(kdf_iterations=70_000)

    def test_frozen_dataclass(self):
        """Test that AuthFileEncryption is immutable."""
        enc = AuthFileEncryption(password="test")
        with pytest.raises(AttributeError):
            enc.password = "new_password"  # type: ignore[misc]


class TestGetAuthPasswordFromEnv:
    """Tests for get_auth_password_from_env function."""

    def test_returns_none_when_not_set(self, monkeypatch):
        """Test returns None when env var is not set."""
        monkeypatch.delenv("AUDIBLE_AUTH_PASSWORD", raising=False)
        assert get_auth_password_from_env() is None

    def test_returns_password_when_set(self, monkeypatch):
        """Test returns password when env var is set."""
        monkeypatch.setenv("AUDIBLE_AUTH_PASSWORD", "my_secret_password")
        assert get_auth_password_from_env() == "my_secret_password"

    def test_returns_empty_string_if_set_empty(self, monkeypatch):
        """Test returns empty string if env var is set to empty."""
        monkeypatch.setenv("AUDIBLE_AUTH_PASSWORD", "")
        assert get_auth_password_from_env() == ""


class TestGetEncryptionConfig:
    """Tests for get_encryption_config function."""

    def test_explicit_password_takes_precedence(self, monkeypatch):
        """Test that explicit password overrides env var."""
        monkeypatch.setenv("AUDIBLE_AUTH_PASSWORD", "env_password")
        config = get_encryption_config(password="explicit_password")
        assert config.password == "explicit_password"

    def test_falls_back_to_env_var(self, monkeypatch):
        """Test falls back to env var when no explicit password."""
        monkeypatch.setenv("AUDIBLE_AUTH_PASSWORD", "env_password")
        config = get_encryption_config()
        assert config.password == "env_password"

    def test_no_password_when_env_disabled(self, monkeypatch):
        """Test no password when env var lookup is disabled."""
        monkeypatch.setenv("AUDIBLE_AUTH_PASSWORD", "env_password")
        config = get_encryption_config(use_env_password=False)
        assert config.password is None

    def test_custom_encryption_settings(self):
        """Test custom encryption and kdf settings."""
        config = get_encryption_config(
            password="test",
            encryption="bytes",
            kdf_iterations=10_000,
        )
        assert config.encryption == "bytes"
        assert config.kdf_iterations == 10_000


class TestLoadAuth:
    """Tests for load_auth function."""

    def test_file_not_found(self, tmp_path):
        """Test raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="Auth file not found"):
            load_auth(tmp_path / "nonexistent.json", None)

    def test_unencrypted_file_loads_without_password(self, tmp_path):
        """Test loading unencrypted file without password."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"test": "data"}')

        mock_auth = MagicMock()
        with patch("src.audible.encryption.detect_file_encryption", return_value=None):
            with patch("src.audible.encryption.Authenticator.from_file", return_value=mock_auth) as mock_from_file:
                result = load_auth(auth_file, None)
                mock_from_file.assert_called_once_with(str(auth_file))
                assert result == mock_auth

    def test_encrypted_file_without_password_raises(self, tmp_path):
        """Test that encrypted file without password raises ValueError."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("encrypted_data")

        with patch("src.audible.encryption.detect_file_encryption", return_value="json"):
            with pytest.raises(ValueError, match="Auth file is encrypted"):
                load_auth(auth_file, AuthFileEncryption())

    def test_encrypted_file_with_password_loads(self, tmp_path):
        """Test loading encrypted file with password."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("encrypted_data")

        mock_auth = MagicMock()
        enc = AuthFileEncryption(password="secret123")

        with patch("src.audible.encryption.detect_file_encryption", return_value="json"):
            with patch("src.audible.encryption.Authenticator.from_file", return_value=mock_auth) as mock_from_file:
                result = load_auth(auth_file, enc)
                mock_from_file.assert_called_once_with(str(auth_file), password="secret123")
                assert result == mock_auth


class TestSaveAuth:
    """Tests for save_auth function."""

    def test_saves_unencrypted_when_no_password(self, tmp_path):
        """Test saving without encryption when no password."""
        auth_file = tmp_path / "subdir" / "auth.json"
        mock_auth = MagicMock()

        def create_file(*args, **kwargs):
            auth_file.parent.mkdir(parents=True, exist_ok=True)
            auth_file.write_text('{"test": "data"}')

        mock_auth.to_file.side_effect = create_file

        save_auth(mock_auth, auth_file, None)

        mock_auth.to_file.assert_called_once_with(str(auth_file), encryption=False)
        assert auth_file.parent.exists()

    def test_saves_encrypted_with_password(self, tmp_path):
        """Test saving with encryption when password provided."""
        auth_file = tmp_path / "auth.json"
        mock_auth = MagicMock()
        enc = AuthFileEncryption(
            password="secret123",
            encryption="json",
            kdf_iterations=10_000,
        )

        def create_file(*args, **kwargs):
            auth_file.write_text("encrypted_content")

        mock_auth.to_file.side_effect = create_file

        save_auth(mock_auth, auth_file, enc)

        mock_auth.to_file.assert_called_once_with(
            str(auth_file),
            password="secret123",
            encryption="json",
            kdf_iterations=10_000,
        )

    def test_saves_with_bytes_encryption(self, tmp_path):
        """Test saving with bytes encryption style."""
        auth_file = tmp_path / "auth.json"
        mock_auth = MagicMock()
        enc = AuthFileEncryption(password="test", encryption="bytes")

        def create_file(*args, **kwargs):
            auth_file.write_text("encrypted_content")

        mock_auth.to_file.side_effect = create_file

        save_auth(mock_auth, auth_file, enc)

        mock_auth.to_file.assert_called_once()
        call_kwargs = mock_auth.to_file.call_args
        assert call_kwargs[1]["encryption"] == "bytes"

    def test_sets_secure_file_permissions(self, tmp_path):
        """Test that save_auth sets file permissions to 600 (owner read/write only)."""
        import stat

        auth_file = tmp_path / "auth.json"
        mock_auth = MagicMock()

        # Make to_file actually create the file so chmod works
        def create_file(*args, **kwargs):
            auth_file.write_text('{"test": "data"}')

        mock_auth.to_file.side_effect = create_file

        save_auth(mock_auth, auth_file, None)

        # Check permissions are 600 (owner read/write only)
        file_mode = auth_file.stat().st_mode & 0o777
        assert file_mode == 0o600, f"Expected 600, got {oct(file_mode)}"

    def test_sets_secure_permissions_with_encryption(self, tmp_path):
        """Test that encrypted file also gets secure permissions."""
        import stat

        auth_file = tmp_path / "auth.json"
        mock_auth = MagicMock()
        enc = AuthFileEncryption(password="test", encryption="json")

        def create_file(*args, **kwargs):
            auth_file.write_text("encrypted_content")

        mock_auth.to_file.side_effect = create_file

        save_auth(mock_auth, auth_file, enc)

        file_mode = auth_file.stat().st_mode & 0o777
        assert file_mode == 0o600, f"Expected 600, got {oct(file_mode)}"


class TestIsFileEncrypted:
    """Tests for is_file_encrypted function."""

    def test_returns_false_for_nonexistent_file(self, tmp_path):
        """Test returns False for non-existent file."""
        assert is_file_encrypted(tmp_path / "nonexistent.json") is False

    def test_returns_true_for_encrypted_file(self, tmp_path):
        """Test returns True for encrypted file."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("encrypted_data")

        with patch("src.audible.encryption.detect_file_encryption", return_value="json"):
            assert is_file_encrypted(auth_file) is True

    def test_returns_false_for_unencrypted_file(self, tmp_path):
        """Test returns False for unencrypted file."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"plain": "text"}')

        with patch("src.audible.encryption.detect_file_encryption", return_value=None):
            assert is_file_encrypted(auth_file) is False


class TestGetFileEncryptionStyle:
    """Tests for get_file_encryption_style function."""

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        """Test returns None for non-existent file."""
        assert get_file_encryption_style(tmp_path / "nonexistent.json") is None

    def test_returns_style_for_encrypted_file(self, tmp_path):
        """Test returns encryption style for encrypted file."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("encrypted_data")

        with patch("src.audible.encryption.detect_file_encryption", return_value="bytes"):
            assert get_file_encryption_style(auth_file) == "bytes"

    def test_returns_none_for_unencrypted_file(self, tmp_path):
        """Test returns None for unencrypted file."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"plain": "text"}')

        with patch("src.audible.encryption.detect_file_encryption", return_value=None):
            assert get_file_encryption_style(auth_file) is None


class TestClientIntegration:
    """Integration tests for encryption with AudibleClient."""

    def test_from_file_with_encrypted_auth(self, tmp_path, monkeypatch):
        """Test AudibleClient.from_file handles encrypted files."""
        from src.audible.client import AudibleClient

        auth_file = tmp_path / "auth.json"
        auth_file.write_text("encrypted_data")

        # Mock the encryption detection and auth loading
        mock_auth = MagicMock()
        mock_auth.locale.country_code = "us"

        # Need to mock Client as well since it validates the auth
        mock_client = MagicMock()

        with patch("src.audible.encryption.detect_file_encryption", return_value="json"):
            with patch("src.audible.encryption.Authenticator.from_file", return_value=mock_auth):
                with patch("src.utils.security.check_file_permissions"):
                    with patch("src.audible.client.Client", return_value=mock_client):
                        client = AudibleClient.from_file(
                            auth_file=auth_file,
                            auth_password="secret123",
                        )
                        assert client is not None

    def test_from_file_encrypted_without_password_raises(self, tmp_path):
        """Test AudibleClient.from_file raises when encrypted file has no password."""
        from src.audible.client import AudibleAuthError, AudibleClient

        auth_file = tmp_path / "auth.json"
        auth_file.write_text("encrypted_data")

        with patch("src.audible.encryption.detect_file_encryption", return_value="json"):
            with patch("src.utils.security.check_file_permissions"):
                # Clear env var to ensure no password is available
                with patch.dict(os.environ, {}, clear=True):
                    with pytest.raises(AudibleAuthError, match="encrypted"):
                        AudibleClient.from_file(auth_file=auth_file)
