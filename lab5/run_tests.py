"""Запустите этот файл кнопкой Run в PyCharm: выполняются все тесты проекта."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    return subprocess.call(
        [sys.executable, "-m", "pytest", "-v", *sys.argv[1:]], cwd=root
    )


if __name__ == "__main__":
    raise SystemExit(main())
