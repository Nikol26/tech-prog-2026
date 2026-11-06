"""Бой, Factory Method локаций, экспедиции и торговец."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from core import Combatant, Dice, Hit


class Enemy:
    def __init__(self, name, health, low, high, experience, gold, defense=0):
        self.name, self.health, self.max_health = name, health, health
        self.low, self.high = low, high
        self.experience, self.gold, self.defense = experience, gold, defense

    def roll_damage(self):
        return Hit(Dice().roll(self.low, self.high))

    def receive_hit(self, damage):
        if damage < 0:
            raise ValueError("Урон не может быть отрицательным")
        dealt = min(self.health, max(1, round(damage * (1 - self.defense))))
        self.health -= dealt
        return dealt


class Goblin(Enemy):
    def __init__(self):
        super().__init__("Гоблин", 50, 6, 14, 40, 30)


class Skeleton(Enemy):
    def __init__(self):
        super().__init__("Скелет", 110, 10, 24, 90, 70, 0.3)


class Dragon(Enemy):
    def __init__(self):
        super().__init__("Дракон", 260, 16, 22, 500, 400, 0.25)

    def roll_damage(self):
        hit = super().roll_damage()
        critical = Dice().chance(0.25)
        return Hit(hit.damage * (2 if critical else 1), critical)


class SwampGuardian(Enemy):
    def __init__(self):
        super().__init__("Болотный страж", 85, 10, 19, 65, 45)

    def receive_hit(self, damage):
        if damage < 0:
            raise ValueError("Урон не может быть отрицательным")
        return super().receive_hit(max(1, damage - 2))


@dataclass(frozen=True)
class BattleEvent:
    round: int
    source: str
    target: str
    damage: int
    health_after: int
    critical: bool


def battle(hero: Combatant, enemy: Combatant):
    events, round_number = [], 0
    while hero.health > 0 and enemy.health > 0:
        round_number += 1
        for attacker, defender in ((hero, enemy), (enemy, hero)):
            hit = attacker.roll_damage()
            damage = defender.receive_hit(hit.damage)
            events.append(BattleEvent(round_number, attacker.name, defender.name,
                                      damage, defender.health, hit.critical))
            if defender.health == 0:
                break
    return hero.health > 0, tuple(events)


@dataclass(frozen=True)
class Expedition:
    seed: int
    enemy: str
    victory: bool
    events: tuple
    experience: int = 0
    gold: int = 0
    loot: object = None
    levels: int = 0


class Location(ABC):
    def __init__(self, catalog):
        self.catalog = catalog

    @abstractmethod
    def create_enemy(self) -> Enemy:
        """Factory Method: тип врага определяет подкласс."""

    def explore(self, hero, seed=None):
        dice = Dice()
        seed = dice.roll(0, 999999) if seed is None else seed
        dice.reseed(seed)
        hero.restore_health()
        enemy = self.create_enemy()
        victory, events = battle(hero, enemy)
        if not victory:
            lost = hero.gold // 2
            hero.spend_gold(lost)
            return Expedition(seed, enemy.name, False, events, gold=-lost)
        gold = dice.roll(enemy.gold // 2, enemy.gold)
        loot = self.catalog.create(dice.pick(self.loot)) if dice.chance(0.6) else None
        if loot is not None:
            if dice.chance(0.3):
                loot.enchant(dice.pick(loot.possible_enchantments))
            hero.inventory.append(loot)
        levels = hero.gain_experience(enemy.experience)
        hero.gold += gold
        return Expedition(seed, enemy.name, True, events, enemy.experience, gold, loot, levels)


class Forest(Location):
    name, level, loot = "Мистический лес", 1, ("iron", "bow", "leather")

    def create_enemy(self):
        return Goblin()


class Crypt(Location):
    name, level, loot = "Заброшенный склеп", 3, ("knight", "bone", "necro", "crypt")

    def create_enemy(self):
        return Skeleton()


class DragonLair(Location):
    name, level, loot = "Логово дракона", 5, ("dawn", "dragon")

    def create_enemy(self):
        return Dragon()


class Swamp(Location):
    name, level, loot = "Туманное болото", 2, ("guardian", "swamp")

    def create_enemy(self):
        return SwampGuardian()


LOCATIONS = (Forest, Swamp, Crypt, DragonLair)


class Merchant:
    stock = ("iron", "elven", "ember", "plate", "guardian")

    def __init__(self, catalog):
        self.catalog = catalog

    def buy(self, hero, code):
        if code not in self.stock:
            raise ValueError("Такого товара нет")
        item = self.catalog.create(code)
        hero.spend_gold(item.price)
        hero.inventory.append(item)
        return item

    def sell(self, hero, item):
        if item not in hero.inventory:
            raise ValueError("Можно продать только предмет из инвентаря")
        hero.inventory.remove(item)
        price = item.price // 2
        hero.gold += price
        return price
