#!/usr/bin/env python3
"""
Version management utilities.

Usage:
    python tools/version.py              # Show current version
    python tools/version.py 0.2.0        # Set specific version
    python tools/version.py patch        # Bump patch (0.1.0 -> 0.1.1)
    python tools/version.py minor        # Bump minor (0.1.0 -> 0.2.0)
    python tools/version.py major        # Bump major (0.1.0 -> 1.0.0)
"""

import re
import sys
from pathlib import Path

# Path to version file
VERSION_FILE = Path(__file__).parent.parent / "src" / "__init__.py"
VERSION_PATTERN = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def get_version() -> str:
    """Get current version from src/__init__.py."""
    content = VERSION_FILE.read_text()
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(f"Could not find __version__ in {VERSION_FILE}")
    return match.group(1)


def set_version(new_version: str) -> None:
    """Set version in src/__init__.py."""
    content = VERSION_FILE.read_text()
    new_content, substitutions = VERSION_PATTERN.subn(f'__version__ = "{new_version}"', content)

    if substitutions == 0:
        raise ValueError(
            f"Could not find __version__ pattern in {VERSION_FILE}\n" f'Expected format: __version__ = "X.Y.Z"'
        )

    VERSION_FILE.write_text(new_content)
    print(f"✅ Updated version to {new_version}")


def bump_version(part: str) -> str:
    """Bump version by part (major, minor, patch)."""
    current = get_version()
    parts = current.split(".")

    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {current}")

    major, minor, patch = map(int, parts)

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid part: {part}. Use major, minor, or patch")

    return f"{major}.{minor}.{patch}"


def main() -> int:
    """Main entry point."""
    if len(sys.argv) == 1:
        # Show current version
        print(f"Current version: {get_version()}")
        return 0

    arg = sys.argv[1]

    if arg in ("major", "minor", "patch"):
        # Bump version
        old_version = get_version()
        new_version = bump_version(arg)
        set_version(new_version)
        print(f"   {old_version} -> {new_version}")
        print(f"\nTo release, run:")
        print(f"   git add src/__init__.py")
        print(f"   git commit -m 'chore: bump version to {new_version}'")
        print(f"   git tag v{new_version}")
        print(f"   git push origin main --tags")
    elif re.match(r"^\d+\.\d+\.\d+$", arg):
        # Set specific version
        old_version = get_version()
        set_version(arg)
        print(f"   {old_version} -> {arg}")
    else:
        print(f"❌ Invalid argument: {arg}")
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
