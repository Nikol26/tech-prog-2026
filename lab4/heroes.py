"""Abstract Factory создаёт семейство, Builder собирает героя."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from core import Hit
from items import Armor, Weapon
from combat import Damage, ArmorHandler, BarrierHandler, EvasionHandler


class StarterKitFactory(ABC):
    def __init__(self, catalog):
        self.catalog = catalog

    @abstractmethod
    def create_weapon(self) -> Weapon: ...

    @abstractmethod
    def create_armor(self) -> Armor: ...


class WarriorKit(StarterKitFactory):
    code, name, health = "warrior", "Воин", 120

    def create_weapon(self):
        return self.catalog.create("sword")

    def create_armor(self):
        return self.catalog.create("mail")


class RangerKit(StarterKitFactory):
    code, name, health = "ranger", "Следопыт", 100

    def create_weapon(self):
        return self.catalog.create("bow")

    def create_armor(self):
        return self.catalog.create("leather")


class MageKit(StarterKitFactory):
    code, name, health = "mage", "Маг", 85

    def create_weapon(self):
        return self.catalog.create("staff")

    def create_armor(self):
        return self.catalog.create("robe")


class PaladinKit(StarterKitFactory):
    code, name, health = "paladin", "Паладин", 110

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
    achievements: set = field(default_factory=set)
    _defense: object = field(init=False, repr=False)

    def __post_init__(self):
        self.rest()

    @property
    def max_health(self):
        return self.hero_class.health + (self.level - 1) * 15

    def rest(self):
        self.health = self.max_health
        self._defense = self.create_defense()

    def restore_health(self):
        self.rest()

    def create_defense(self):
        code = self.hero_class.code
        evasion = 0.15 if code == "ranger" else 0.10 if code == "mage" and self.level >= 3 else 0
        barrier = 30 if code == "mage" else 20 if code == "warrior" and self.level >= 3 else 0
        if code == "ranger" and self.level >= 5:
            barrier = 15
        if code == "paladin":
            barrier = 15
        armor = ArmorHandler(self.armor.defense / 100)
        first = armor
        if evasion:
            first = EvasionHandler(evasion)
            first.set_next(armor)
        if barrier:
            armor.set_next(BarrierHandler(barrier))
        return first

    def roll_damage(self):
        hit = self.weapon.roll_damage()
        return Hit(hit.damage + (self.level - 1) * 3, hit.critical)

    def receive_hit(self, damage):
        result = Damage(damage)
        self._defense.handle(result)
        result.amount = min(self.health, result.amount)
        self.health -= result.amount
        return result

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
        self._defense = self.create_defense()


class HeroBuilder:
    def __init__(self, catalog):
        self.catalog = catalog
        self.name, self.kind, self.level, self.gold = "", None, 1, 50
        self.experience, self.inventory, self.achievements = 0, [], set()
        self.weapon, self.armor = None, None

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

    def set_experience(self, value):
        self.experience = value
        return self

    def set_equipment(self, weapon, armor):
        self.weapon, self.armor = weapon, armor
        return self

    def set_inventory(self, items):
        self.inventory = list(items)
        return self

    def set_achievements(self, values):
        self.achievements = set(values)
        return self

    def build(self):
        if not 1 <= len(self.name) <= 20:
            raise ValueError("Имя должно содержать от 1 до 20 символов")
        if self.kind not in KITS:
            raise ValueError("Не выбран класс героя")
        if self.level < 1 or self.gold < 0:
            raise ValueError("Уровень должен быть положительным, золото — неотрицательным")
        if type(self.level) is not int or type(self.gold) is not int:
            raise ValueError("Уровень и золото должны быть целыми числами")
        if type(self.experience) is not int or not 0 <= self.experience < self.level * 100:
            raise ValueError("Некорректный опыт героя")
        if self.achievements - {"first-blood", "lucky", "veteran", "dragon-slayer"}:
            raise ValueError("Неизвестное достижение")
        kit = self.kind(self.catalog)
        weapon = self.weapon if self.weapon is not None else kit.create_weapon()
        armor = self.armor if self.armor is not None else kit.create_armor()
        if not isinstance(weapon, Weapon) or not isinstance(armor, Armor):
            raise ValueError("Нужны оружие и броня соответствующих типов")
        return Hero(self.name, self.kind, weapon.copy(), armor.copy(), self.level, self.gold,
                    self.experience, [item.copy() for item in self.inventory],
                    achievements=self.achievements.copy())
