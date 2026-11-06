"""Abstract Factory создаёт семейство, Builder собирает героя."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from core import Hit
from items import Armor, Weapon


class StarterKitFactory(ABC):
    def __init__(self, catalog):
        self.catalog = catalog

    @abstractmethod
    def create_weapon(self) -> Weapon: ...

    @abstractmethod
    def create_armor(self) -> Armor: ...


class WarriorKit(StarterKitFactory):
    name, health = "Воин", 120

    def create_weapon(self):
        return self.catalog.create("sword")

    def create_armor(self):
        return self.catalog.create("mail")


class RangerKit(StarterKitFactory):
    name, health = "Следопыт", 100

    def create_weapon(self):
        return self.catalog.create("bow")

    def create_armor(self):
        return self.catalog.create("leather")


class MageKit(StarterKitFactory):
    name, health = "Маг", 85

    def create_weapon(self):
        return self.catalog.create("staff")

    def create_armor(self):
        return self.catalog.create("robe")


class PaladinKit(StarterKitFactory):
    name, health = "Паладин", 110

    def create_weapon(self):
        return self.catalog.create("hammer")

    def create_armor(self):
        return self.catalog.create("blessed")


KITS = (WarriorKit, RangerKit, MageKit, PaladinKit)


@dataclass
class Hero:
    name: str
    hero_class: type
    weapon: Weapon
    armor: Armor
    level: int = 1
    gold: int = 50
    experience: int = 0
    inventory: list = field(default_factory=list)
    health: int = field(init=False)

    def __post_init__(self):
        self.restore_health()

    @property
    def max_health(self):
        return self.hero_class.health + (self.level - 1) * 15

    def restore_health(self):
        self.health = self.max_health

    def roll_damage(self):
        hit = self.weapon.roll_damage()
        return Hit(hit.damage + (self.level - 1) * 3, hit.critical)

    def receive_hit(self, damage):
        if damage < 0:
            raise ValueError("Урон не может быть отрицательным")
        dealt = min(self.health, max(1, round(damage * (1 - self.armor.defense / 100))))
        self.health -= dealt
        return dealt

    def gain_experience(self, amount):
        if amount < 0:
            raise ValueError("Опыт не может быть отрицательным")
        self.experience += amount
        gained = 0
        while self.experience >= self.level * 100:
            self.experience -= self.level * 100
            self.level += 1
            gained += 1
        return gained

    def spend_gold(self, amount):
        if amount < 0 or amount > self.gold:
            raise ValueError(f"Не хватает золота или неверная сумма: {amount}, есть {self.gold}")
        self.gold -= amount

    def equip(self, item):
        if item not in self.inventory:
            raise ValueError("Предмета нет в инвентаре")
        slot = "weapon" if isinstance(item, Weapon) else "armor"
        if not isinstance(item, (Weapon, Armor)):
            raise ValueError("Этот предмет нельзя экипировать")
        self.inventory.remove(item)
        self.inventory.append(getattr(self, slot))
        setattr(self, slot, item)


class HeroBuilder:
    def __init__(self, catalog):
        self.catalog = catalog
        self.name, self.kind, self.level, self.gold = "", None, 1, 50

    def set_name(self, name):
        self.name = name.strip()
        return self

    def set_class(self, kind):
        self.kind = kind
        return self

    def set_level(self, level):
        self.level = level
        return self

    def set_gold(self, gold):
        self.gold = gold
        return self

    def build(self):
        if not 1 <= len(self.name) <= 20:
            raise ValueError("Имя должно содержать от 1 до 20 символов")
        if self.kind not in KITS:
            raise ValueError("Не выбран класс героя")
        if self.level < 1 or self.gold < 0:
            raise ValueError("Уровень должен быть положительным, золото — неотрицательным")
        kit = self.kind(self.catalog)
        return Hero(self.name, self.kind, kit.create_weapon(), kit.create_armor(),
                    self.level, self.gold)
