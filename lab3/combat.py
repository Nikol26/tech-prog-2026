"""Chain of Responsibility и Strategy: защита и решения в бою."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from core import Dice


@dataclass
class Damage:
    amount: int
    evaded: bool = False
    absorbed: int = 0

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Урон не может быть отрицательным")


class DamageHandler(ABC):
    def __init__(self):
        self.next = None

    def set_next(self, handler):
        self.next = handler
        return handler

    def handle(self, damage):
        if damage.amount > 0:
            self.apply(damage)
            if self.next is not None and not damage.evaded and damage.amount > 0:
                self.next.handle(damage)

    @abstractmethod
    def apply(self, damage): ...


class EvasionHandler(DamageHandler):
    def __init__(self, chance):
        super().__init__()
        if not 0 <= chance <= 1:
            raise ValueError("Вероятность должна быть от 0 до 1")
        self.chance = chance

    def apply(self, damage):
        if Dice().chance(self.chance):
            damage.amount, damage.evaded = 0, True


class ArmorHandler(DamageHandler):
    def __init__(self, defense):
        super().__init__()
        if not 0 <= defense <= 1:
            raise ValueError("Защита должна быть от 0 до 1")
        self.defense = defense

    def apply(self, damage):
        damage.amount = max(1, int(damage.amount * (1 - self.defense) + 0.5))


class BarrierHandler(DamageHandler):
    def __init__(self, strength):
        super().__init__()
        if strength < 0:
            raise ValueError("Барьер не может быть отрицательным")
        self.remaining = strength

    def apply(self, damage):
        absorbed = min(self.remaining, damage.amount)
        self.remaining -= absorbed
        damage.amount -= absorbed
        damage.absorbed += absorbed


class Action(Enum):
    ATTACK = ("Обычный удар", 1.0, 1.0)
    POWER_STRIKE = ("Безрассудный удар", 1.5, 1.5)
    DEFEND = ("Оборона", 0.5, 0.3)

    def __init__(self, title, attack, incoming):
        self.title, self.attack, self.incoming = title, attack, incoming


class Tactic(ABC):
    @abstractmethod
    def choose_action(self, round_number, hero, enemy): ...


class BalancedTactic(Tactic):
    code, name = "balanced", "Баланс"
    description = "обычные удары без изменения урона"

    def choose_action(self, round_number, hero, enemy):
        return Action.ATTACK


class AggressiveTactic(Tactic):
    code, name = "aggressive", "Натиск"
    description = "если HP врага больше HP героя: урон и ответный удар x1.5"

    def choose_action(self, round_number, hero, enemy):
        return Action.POWER_STRIKE if enemy.health > hero.health else Action.ATTACK


class CautiousTactic(Tactic):
    code, name = "cautious", "Осторожность"
    description = "при HP ниже 40% в чётные раунды: свой урон x0.5, входящий x0.3"

    def choose_action(self, round_number, hero, enemy):
        if hero.health < hero.max_health * 0.4 and round_number % 2 == 0:
            return Action.DEFEND
        return Action.ATTACK


TACTICS = (BalancedTactic(), AggressiveTactic(), CautiousTactic())
