#!/usr/bin/env python3
"""
RetroBIOS setup helper.

Checks for ~/retrobios/bios.py. If it is missing, searches the current
folder for a supported BIOS source file and copies it into ~/retrobios.
Then creates ~/.local/bin/retrobios so the app can be launched with `retrobios`.

Usage:
    python3 "retro bios_setup_EN.py"
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

HOME = Path.home()
APP_DIR = HOME / "retrobios"
APP_FILE = APP_DIR / "bios.py"
BIN_DIR = HOME / ".local" / "bin"
COMMAND_FILE = BIN_DIR / "retrobios"

SOURCE_NAMES = (
    "RetroBIOS_naprawiony_v3.py",
    "RetroBIOS_naprawiony.py",
    "bios.py",
)


def find_source(script_dir: Path) -> Path | None:
    for name in SOURCE_NAMES:
        candidate = script_dir / name
        if candidate.is_file() and candidate.resolve() != APP_FILE.resolve():
            return candidate
    return None


def write_launcher() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    launcher = """#!/usr/bin/env bash
set -e
APP="$HOME/retrobios/bios.py"
if [ ! -f "$APP" ]; then
    echo "Program not found: $APP" >&2
    echo "Run the setup script again with the source file next to it." >&2
    exit 1
fi
exec python3 "$APP" "$@"
"""
    COMMAND_FILE.write_text(launcher, encoding="utf-8")
    COMMAND_FILE.chmod(COMMAND_FILE.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    APP_DIR.mkdir(parents=True, exist_ok=True)

    if APP_FILE.is_file():
        print(f"Found program: {APP_FILE}")
    else:
        source = find_source(script_dir)
        if source is None:
            print(f"Could not find {APP_FILE}.", file=sys.stderr)
            print("Place one of these files next to this script:", file=sys.stderr)
            for name in SOURCE_NAMES:
                print(f"  - {name}", file=sys.stderr)
            return 1
        shutil.copy2(source, APP_FILE)
        print(f"Copied {source.name} -> {APP_FILE}")

    # Create the command even if the app already existed.
    write_launcher()

    # Validate the Python source without launching the curses UI.
    import py_compile
    try:
        py_compile.compile(str(APP_FILE), doraise=True)
        print("Python syntax check: OK")
    except py_compile.PyCompileError as exc:
        print(f"WARNING: syntax error in {APP_FILE}:\n{exc}", file=sys.stderr)
        return 1

    print(f"Created command: {COMMAND_FILE}")
    if str(BIN_DIR) not in os.environ.get("PATH", "").split(os.pathsep):
        print("\nAdd this directory to PATH for the current terminal:")
        print('  export PATH="$HOME/.local/bin:$PATH"')
        print("To keep this change in Bash, add the line to ~/.bashrc.")
    print("\nDone. Launch the program with: retrobios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
