"""Игра запускается отдельным Python-процессом с настоящим консольным вводом."""
from pathlib import Path
import os
import subprocess
import sys
import pytest


GAME_DIRECTORY = Path(__file__).resolve().parents[2] / "lab4"


def run_game(save_file, commands):
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    # Меняется только путь сохранения; используются настоящие main, input, print и файлы.
    return subprocess.run(
        [sys.executable, "-c", "from main import main; import sys; main(sys.argv[1])", str(save_file)],
        cwd=GAME_DIRECTORY, input=commands, text=True, encoding="utf-8",
        capture_output=True, timeout=30, env=environment, check=True
    )


@pytest.mark.e2e
class TestConsoleGame:
    @pytest.mark.smoke
    def test_game_opens_menu_and_exits_without_creating_save(self, tmp_path):
        file = tmp_path / "heroes.json"
        result = run_game(file, "0\n")
        assert "создать героя" in result.stdout
        assert result.stderr == ""
        assert not file.exists()

    def test_create_expedition_save_restart_and_load(self, tmp_path):
        file = tmp_path / "heroes.json"
        # Создать -> воин -> имя -> лес -> баланс -> seed 7 -> сохранить и выйти.
        first = run_game(file, "1\n1\nНиколь\n1\n1\n1\n7\n0\n")
        assert "Победа!" in first.stdout
        assert "Новое достижение: Первая кровь" in first.stdout
        assert "Игра сохранена." in first.stdout
        assert file.exists()
        before = file.read_bytes()
        second = run_game(file, "2\n1\n0\n")
        assert "Николь" in second.stdout
        assert "Первая кровь" in second.stdout
        assert "Имя героя:" not in second.stdout
        assert "Игра сохранена." in second.stdout
        assert file.read_bytes() == before
