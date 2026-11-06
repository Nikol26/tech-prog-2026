"""Общий источник случайности и контракт участника боя."""
from dataclasses import dataclass
import random
from typing import Protocol


class Dice:
    """Singleton: повторный Dice() возвращает тот же объект."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._random = random.Random()
        return cls._instance

    def reseed(self, seed):
        self._random.seed(seed)

    def roll(self, low, high):
        return self._random.randint(low, high)

    def chance(self, probability):
        return self._random.random() < probability

    def pick(self, options):
        return self._random.choice(options)


@dataclass(frozen=True)
class Hit:
    damage: int
    critical: bool = False


class Combatant(Protocol):
    name: str
    health: int

    def roll_damage(self) -> Hit: ...
    def receive_hit(self, damage: int) -> int: ...
