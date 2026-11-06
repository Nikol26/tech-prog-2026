"""Prototype: каталог выдаёт независимые копии предметов."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from copy import copy
from core import Dice, Hit


@dataclass(frozen=True)
class Enchantment:
    name: str
    damage: int = 0
    defense: int = 0
    price: int = 20


FIERY = Enchantment("Огненное", damage=6, price=50)
SHARP = Enchantment("Острое", damage=3)
STURDY = Enchantment("Прочное", defense=5)


@dataclass(eq=False)
class Item(ABC):
    code: str
    name: str
    base_price: int
    power: int
    enchantments: list = field(default_factory=list)

    def copy(self):
        clone = copy(self)
        clone.enchantments = self.enchantments.copy()
        return clone

    def enchant(self, enchantment):
        if enchantment not in self.possible_enchantments:
            raise ValueError("Зачарование не подходит этому предмету")
        self.enchantments.append(enchantment)

    @property
    def price(self):
        return self.base_price + sum(e.price for e in self.enchantments)

    @property
    @abstractmethod
    def possible_enchantments(self): ...

    @property
    @abstractmethod
    def description(self): ...

    def __str__(self):
        names = ", ".join(e.name for e in self.enchantments)
        return f"{self.name}" + (f" [{names}]" if names else "") + f" ({self.description})"


class Weapon(Item):
    possible_enchantments = (SHARP, FIERY)

    @property
    def damage(self):
        return self.power + sum(e.damage for e in self.enchantments)

    @property
    def description(self):
        return f"базовый урон {self.damage}"

    @abstractmethod
    def roll_damage(self): ...


class Sword(Weapon):
    def roll_damage(self):
        return Hit(self.damage)


class Bow(Weapon):
    def roll_damage(self):
        critical = Dice().chance(0.3)
        return Hit(self.damage * (2 if critical else 1), critical)


class Staff(Weapon):
    def roll_damage(self):
        return Hit(Dice().roll(round(self.damage * 0.7), round(self.damage * 1.3)))


class Hammer(Weapon):
    def roll_damage(self):
        critical = Dice().chance(0.2)
        return Hit(self.damage * (2 if critical else 1), critical)


class Armor(Item):
    possible_enchantments = (STURDY,)

    @property
    def defense(self):
        return min(80, self.power + sum(e.defense for e in self.enchantments))

    @property
    def description(self):
        return f"защита {self.defense}%"


class ItemCatalog:
    def __init__(self):
        self._prototypes = {}

    def register(self, item):
        self._prototypes[item.code] = item.copy()

    def create(self, code):
        if code not in self._prototypes:
            raise ValueError(f"Неизвестный предмет: {code}")
        return self._prototypes[code].copy()


def create_catalog():
    catalog = ItemCatalog()
    # Тип, код, название, цена и характеристика шаблона.
    for kind, rows in (
        (Sword, [("sword", "Тренировочный меч", 20, 12),
                 ("iron", "Железный меч", 80, 17),
                 ("knight", "Клинок рыцаря", 150, 23),
                 ("dawn", "Клинок рассвета", 500, 35)]),
        (Bow, [("bow", "Охотничий лук", 20, 10),
               ("elven", "Эльфийский лук", 90, 14),
               ("bone", "Костяной лук", 140, 17)]),
        (Staff, [("staff", "Посох ученика", 20, 14),
                 ("ember", "Тлеющий посох", 90, 20),
                 ("necro", "Посох некроманта", 150, 25)]),
        (Hammer, [("hammer", "Молот послушника", 30, 11),
                  ("guardian", "Молот болотного стража", 110, 20)]),
        (Armor, [("mail", "Кольчуга", 40, 30), ("leather", "Кожаная броня", 30, 20),
                 ("robe", "Льняная роба", 15, 10), ("blessed", "Освящённая броня", 45, 25),
                 ("plate", "Латы", 120, 40), ("crypt", "Броня склепа", 160, 45),
                 ("swamp", "Броня болотного стража", 100, 35),
                 ("dragon", "Драконья чешуя", 500, 55)]),
    ):
        for row in rows:
            catalog.register(kind(*row))
    return catalog
