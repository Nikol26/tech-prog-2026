"""Общие исходные данные. Настоящие сохранения игры тесты не используют."""
import pytest
from core import Dice
from heroes import HeroBuilder, WarriorKit
from items import create_catalog


@pytest.fixture(autouse=True)
def deterministic_dice():
    dice = Dice()
    previous = dice._random.getstate()
    dice.reseed(2026)
    yield
    dice._random.setstate(previous)


@pytest.fixture
def catalog():
    return create_catalog()


@pytest.fixture
def hero(catalog):
    return HeroBuilder(catalog).set_name("Артур").set_class(WarriorKit).build()
