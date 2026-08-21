"""Select the app-local virtual environment before importing the GUI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _local_python(app_directory: Path) -> Path:
    if os.name == "nt":
        return app_directory / ".venv" / "Scripts" / "python.exe"
    return app_directory / ".venv" / "bin" / "python"


def run() -> None:
    app_directory = Path(__file__).resolve().parents[1]
    local_python = _local_python(app_directory)
    if (
        local_python.is_file()
        and local_python.resolve() != Path(sys.executable).resolve()
    ):
        command = [str(local_python), str(app_directory / "app.py")]
        raise SystemExit(subprocess.call(command, cwd=app_directory))

    from .gui import main

    main()
