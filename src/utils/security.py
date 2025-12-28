"""
Security utilities for handling sensitive files and data.

Provides:
- File permission checking and fixing
- Secure file creation helpers
- Permission validation for credentials
"""

import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

# Recommended permission masks
SECURE_FILE_MODE = 0o600  # Owner read/write only
SECURE_DIR_MODE = 0o700  # Owner read/write/execute only

# Permission bits that indicate world/group access
INSECURE_BITS = stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH


def check_file_permissions(path: Path, fix: bool = False, warn: bool = True) -> bool:
    """
    Check if a file has secure permissions (owner-only access).

    Args:
        path: Path to the file to check
        fix: If True, automatically fix insecure permissions
        warn: If True, log a warning for insecure permissions

    Returns:
        True if permissions are secure (or were fixed), False otherwise

    Example:
        # Just check and warn
        check_file_permissions(Path("./data/audible_auth.json"))

        # Check and auto-fix
        check_file_permissions(Path("./data/audible_auth.json"), fix=True)
    """
    if not path.exists():
        return True  # Non-existent files don't have permission issues

    try:
        current_mode = path.stat().st_mode
        current_perms = stat.S_IMODE(current_mode)

        # Check if group or others have any access
        if current_perms & INSECURE_BITS:
            if warn:
                logger.warning(
                    "File '%s' has insecure permissions (%o). " "Recommended: %o (owner read/write only)",
                    path,
                    current_perms,
                    SECURE_FILE_MODE,
                )

            if fix:
                return fix_file_permissions(path)

            return False

        return True

    except OSError as e:
        logger.error("Failed to check permissions for '%s': %s", path, e)
        return False


def fix_file_permissions(path: Path, mode: int = SECURE_FILE_MODE) -> bool:
    """
    Fix file permissions to be secure (owner-only access).

    Args:
        path: Path to the file to fix
        mode: Permission mode to set (default: 0o600)

    Returns:
        True if permissions were successfully fixed, False otherwise
    """
    if not path.exists():
        return False

    try:
        os.chmod(path, mode)
        logger.info("Fixed permissions for '%s' to %o", path, mode)
        return True
    except OSError as e:
        logger.error("Failed to fix permissions for '%s': %s", path, e)
        return False


def fix_directory_permissions(path: Path, mode: int = SECURE_DIR_MODE) -> bool:
    """
    Fix directory permissions to be secure.

    Args:
        path: Path to the directory to fix
        mode: Permission mode to set (default: 0o700)

    Returns:
        True if permissions were successfully fixed, False otherwise
    """
    return fix_file_permissions(path, mode)


def secure_file_create(path: Path, content: str | bytes, mode: int = SECURE_FILE_MODE) -> bool:
    """
    Create a file with secure permissions atomically.

    The file is created with restricted permissions from the start,
    avoiding any window where it might be readable by others.

    Args:
        path: Path where to create the file
        content: Content to write (str or bytes)
        mode: Permission mode (default: 0o600)

    Returns:
        True if file was created successfully, False otherwise
    """
    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Set umask to ensure file is created with correct permissions
        old_umask = os.umask(0o077)
        try:
            # Open with explicit mode
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(path, flags, mode)
            try:
                if isinstance(content, str):
                    content = content.encode("utf-8")
                os.write(fd, content)
            finally:
                os.close(fd)
        finally:
            os.umask(old_umask)

        logger.debug("Created secure file '%s' with mode %o", path, mode)
        return True

    except OSError as e:
        logger.error("Failed to create secure file '%s': %s", path, e)
        return False


def get_permission_string(path: Path) -> str:
    """
    Get a human-readable permission string for a file.

    Args:
        path: Path to the file

    Returns:
        Permission string like "rw-------" or "rw-r--r--"
    """
    if not path.exists():
        return "not found"

    try:
        mode = path.stat().st_mode
        perms = stat.S_IMODE(mode)

        result = ""
        for who in ["USR", "GRP", "OTH"]:
            r = perms & getattr(stat, f"S_IR{who}")
            w = perms & getattr(stat, f"S_IW{who}")
            x = perms & getattr(stat, f"S_IX{who}")
            result += "r" if r else "-"
            result += "w" if w else "-"
            result += "x" if x else "-"

        return result
    except OSError:
        return "error"


def is_file_secure(path: Path) -> bool:
    """
    Quick check if a file has secure permissions.

    Args:
        path: Path to check

    Returns:
        True if file is secure or doesn't exist, False if insecure
    """
    if not path.exists():
        return True

    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        return not (mode & INSECURE_BITS)
    except OSError:
        return False


def ensure_secure_directory(path: Path) -> bool:
    """
    Ensure a directory exists with secure permissions.

    Creates the directory if it doesn't exist, and fixes
    permissions if they are insecure.

    Args:
        path: Directory path

    Returns:
        True if directory exists and is secure, False otherwise
    """
    try:
        if not path.exists():
            old_umask = os.umask(0o077)
            try:
                path.mkdir(parents=True, mode=SECURE_DIR_MODE)
            finally:
                os.umask(old_umask)
            logger.debug("Created secure directory '%s'", path)
            return True

        if path.is_dir():
            # Use directory mode (700) not file mode (600)
            return fix_directory_permissions(path)

        logger.error("Path '%s' exists but is not a directory", path)
        return False

    except OSError as e:
        logger.error("Failed to ensure secure directory '%s': %s", path, e)
        return False
