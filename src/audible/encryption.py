"""
Authentication file encryption support.

Provides helpers for loading/saving encrypted Audible auth files
using the audible library's built-in AES encryption.

The audible library uses AES-CBC with PBKDF2 key derivation.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from audible import Authenticator
from audible.aescipher import detect_file_encryption

logger = logging.getLogger(__name__)

EncryptionStyle = Literal["json", "bytes"]


@dataclass(frozen=True)
class AuthFileEncryption:
    """
    Configuration for auth file encryption.

    Attributes:
        password: Encryption password. If None, file is stored unencrypted.
        encryption: Encryption format ('json' or 'bytes'). Ignored if password is None.
        kdf_iterations: PBKDF2 iterations for key derivation (max 65535).
                       Higher = more secure but slower. Default 50000.
    """

    password: str | None = None
    encryption: EncryptionStyle = "json"
    kdf_iterations: int = 50_000

    def __post_init__(self):
        if self.kdf_iterations < 1 or self.kdf_iterations > 65535:
            raise ValueError("kdf_iterations must be between 1 and 65535")


def get_auth_password_from_env() -> str | None:
    """
    Get auth encryption password from environment variable.

    Returns:
        Password string if AUDIBLE_AUTH_PASSWORD is set, None otherwise.
    """
    return os.environ.get("AUDIBLE_AUTH_PASSWORD")


def get_encryption_config(
    password: str | None = None,
    encryption: EncryptionStyle = "json",
    kdf_iterations: int = 50_000,
    use_env_password: bool = True,
) -> AuthFileEncryption:
    """
    Build encryption config, optionally using env var for password.

    Args:
        password: Explicit password (takes precedence over env var)
        encryption: Encryption style ('json' or 'bytes')
        kdf_iterations: PBKDF2 iterations
        use_env_password: If True, fall back to AUDIBLE_AUTH_PASSWORD env var

    Returns:
        Configured AuthFileEncryption instance
    """
    effective_password = password
    if effective_password is None and use_env_password:
        effective_password = get_auth_password_from_env()

    return AuthFileEncryption(
        password=effective_password,
        encryption=encryption,
        kdf_iterations=kdf_iterations,
    )


def load_auth(
    auth_path: Path,
    enc: AuthFileEncryption | None = None,
) -> Authenticator:
    """
    Load Authenticator from file, handling encryption automatically.

    Detects whether the file is encrypted and loads accordingly.

    Args:
        auth_path: Path to the auth file
        enc: Encryption config. If None, attempts unencrypted load.

    Returns:
        Loaded Authenticator instance

    Raises:
        ValueError: If file is encrypted but no password provided
        FileNotFoundError: If auth file doesn't exist
    """
    if not auth_path.exists():
        raise FileNotFoundError(f"Auth file not found: {auth_path}")

    # Detect whether the existing file is encrypted
    detected = detect_file_encryption(auth_path)

    if detected:
        logger.debug("Detected encrypted auth file (style: %s)", detected)
        if not enc or not enc.password:
            raise ValueError(
                f"Auth file is encrypted ({detected}) but no password was provided. "
                "Set AUDIBLE_AUTH_PASSWORD environment variable or pass --auth-password."
            )
        # Encryption style is auto-detected by Authenticator.from_file
        return Authenticator.from_file(str(auth_path), password=enc.password)

    # Not encrypted - load directly
    logger.debug("Loading unencrypted auth file")
    return Authenticator.from_file(str(auth_path))


def save_auth(
    auth: Authenticator,
    auth_path: Path,
    enc: AuthFileEncryption | None = None,
) -> None:
    """
    Save Authenticator to file, optionally encrypted.

    Sets secure file permissions (600 - owner read/write only).

    Args:
        auth: Authenticator instance to save
        auth_path: Path to save the auth file
        enc: Encryption config. If None or no password, saves unencrypted.
    """
    # Ensure parent directory exists
    auth_path.parent.mkdir(parents=True, exist_ok=True)

    if enc and enc.password:
        logger.info("Saving encrypted auth file (style: %s)", enc.encryption)
        auth.to_file(
            str(auth_path),
            password=enc.password,
            encryption=enc.encryption,
            kdf_iterations=enc.kdf_iterations,
        )
    else:
        logger.warning("Saving auth file WITHOUT encryption. " "Consider setting AUDIBLE_AUTH_PASSWORD for security.")
        auth.to_file(str(auth_path), encryption=False)

    # Set secure permissions: owner read/write only (600)
    auth_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    logger.debug("Set file permissions to 600 on %s", auth_path)


def is_file_encrypted(auth_path: Path) -> bool:
    """
    Check if an auth file is encrypted.

    Args:
        auth_path: Path to the auth file

    Returns:
        True if file is encrypted, False otherwise
    """
    if not auth_path.exists():
        return False
    return bool(detect_file_encryption(auth_path))


def get_file_encryption_style(auth_path: Path) -> str | None:
    """
    Get the encryption style of an auth file.

    Args:
        auth_path: Path to the auth file

    Returns:
        'json', 'bytes', or None if not encrypted
    """
    if not auth_path.exists():
        return None
    detected = detect_file_encryption(auth_path)
    return detected if detected else None
