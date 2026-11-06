"""Мир игры: Factory Method, Decorator и Adapter."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from core import Combatant, Dice, Hit
from combat import Damage, ArmorHandler, BarrierHandler, BalancedTactic


class Enemy:
    code = "enemy"

    def __init__(self, name, health, low, high, experience, gold, defense=0, barrier=0):
        self.name, self.health, self.max_health = name, health, health
        self.low, self.high = low, high
        self.experience, self.gold = experience, gold
        self._defense = ArmorHandler(defense)
        if barrier:
            self._defense.set_next(BarrierHandler(barrier))

    def roll_damage(self):
        return Hit(Dice().roll(self.low, self.high))

    def roll_gold_reward(self):
        return Dice().roll(self.gold // 2, self.gold)

    def receive_hit(self, amount):
        damage = Damage(amount)
        self._defense.handle(damage)
        damage.amount = min(self.health, damage.amount)
        self.health -= damage.amount
        return damage


class Goblin(Enemy):
    code = "goblin"

    def __init__(self):
        super().__init__("Гоблин", 50, 6, 14, 40, 30)


class Skeleton(Enemy):
    code = "skeleton"

    def __init__(self):
        super().__init__("Скелет", 110, 10, 24, 90, 70, defense=0.3)


class Dragon(Enemy):
    code = "dragon"

    def __init__(self):
        super().__init__("Дракон", 260, 16, 22, 500, 400, defense=0.25, barrier=40)

    def roll_damage(self):
        hit = super().roll_damage()
        critical = Dice().chance(0.25)
        return Hit(hit.damage * (2 if critical else 1), critical)


class SwampGuardian(Enemy):
    code = "swamp-guardian"

    def __init__(self):
        super().__init__("Болотный страж", 85, 10, 19, 65, 45, barrier=15)


class EnemyDecorator(Enemy):
    """Общий интерфейс врага сохранён; обёртки можно вкладывать."""
    prefix = ""

    def __init__(self, enemy):
        self.enemy = enemy

    @property
    def code(self):
        return self.enemy.code

    @property
    def name(self):
        return self.prefix + self.enemy.name

    @property
    def experience(self):
        return self.enemy.experience

    def __getattr__(self, name):
        return getattr(self.enemy, name)

    def roll_damage(self):
        return self.enemy.roll_damage()

    def roll_gold_reward(self):
        return self.enemy.roll_gold_reward()

    def receive_hit(self, amount):
        return self.enemy.receive_hit(amount)


class LegendaryEnemy(EnemyDecorator):
    prefix = "Легендарный "

    def roll_damage(self):
        hit = self.enemy.roll_damage()
        return Hit(hit.damage * 2, hit.critical)

    @property
    def experience(self):
        return self.enemy.experience * 2

    def roll_gold_reward(self):
        return self.enemy.roll_gold_reward() * 2


class WindfuryEnemy(EnemyDecorator):
    prefix = "Неистовый "

    def roll_damage(self):
        first, second = self.enemy.roll_damage(), self.enemy.roll_damage()
        return Hit(first.damage + second.damage, first.critical or second.critical)

    @property
    def experience(self):
        return self.enemy.experience * 3 // 2

    def roll_gold_reward(self):
        return self.enemy.roll_gold_reward() * 3 // 2


class ArmoredEnemy(EnemyDecorator):
    prefix = "Бронированный "

    def receive_hit(self, amount):
        Damage(amount)  # Проверяем исходный урон до преобразования.
        return self.enemy.receive_hit(amount - amount // 2)


class HauntedWeapon(Enemy):
    """Adapter: превращает предмет Weapon в противника Enemy."""
    code = "haunted-weapon"

    def __init__(self, weapon):
        self.weapon = weapon
        super().__init__("Одержимый " + weapon.name, weapon.damage * 5,
                         0, 0, weapon.price // 2, weapon.price // 2)

    def roll_damage(self):
        return self.weapon.roll_damage()


@dataclass(frozen=True)
class BattleEvent:
    round: int
    source: str
    target: str
    damage: int
    health_after: int
    critical: bool
    evaded: bool = False
    absorbed: int = 0
    action: str = "ATTACK"


def battle(hero: Combatant, enemy: Combatant, tactic=None):
    tactic = tactic if tactic is not None else BalancedTactic()
    events, round_number = [], 0
    while hero.health > 0 and enemy.health > 0:
        round_number += 1
        action = tactic.choose_action(round_number, hero, enemy)
        for attacker, defender, multiplier in ((hero, enemy, action.attack),
                                               (enemy, hero, action.incoming)):
            hit = attacker.roll_damage()
            damage = defender.receive_hit(max(1, int(hit.damage * multiplier + 0.5)))
            events.append(BattleEvent(round_number, attacker.name, defender.name,
                                      damage.amount, defender.health, hit.critical,
                                      damage.evaded, damage.absorbed, action.name))
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
    location_code: str = ""
    tactic_code: str = "balanced"
    enemy_code: str = ""


class Location(ABC):
    def __init__(self, catalog):
        self.catalog = catalog

    @abstractmethod
    def create_enemy(self) -> Enemy:
        """Factory Method: тип врага определяет подкласс."""

    def _make_elite(self, enemy, dice):
        both = dice.chance(0.25)
        if dice.chance(0.5):
            enemy = LegendaryEnemy(enemy)
            if both:
                enemy = WindfuryEnemy(enemy)
        else:
            enemy = WindfuryEnemy(enemy)
            if both:
                enemy = LegendaryEnemy(enemy)
        return ArmoredEnemy(enemy) if dice.chance(0.3) else enemy

    def explore(self, hero, seed=None, tactic=None):
        dice = Dice()
        seed = dice.roll(0, 999999) if seed is None else seed
        dice.reseed(seed)
        tactic = tactic if tactic is not None else BalancedTactic()
        hero.rest()
        enemy = self.create_enemy()
        if dice.chance(0.2):
            enemy = self._make_elite(enemy, dice)
        victory, events = battle(hero, enemy, tactic)
        context = dict(location_code=self.code, tactic_code=tactic.code, enemy_code=enemy.code)
        if not victory:
            lost = hero.gold // 2
            hero.spend_gold(lost)
            return Expedition(seed, enemy.name, False, events, gold=-lost, **context)
        gold = enemy.roll_gold_reward()
        loot = self.catalog.create(dice.pick(self.loot)) if dice.chance(0.6) else None
        if loot is not None:
            if dice.chance(0.3):
                loot.enchant(dice.pick(loot.possible_enchantments))
            hero.inventory.append(loot)
        levels = hero.gain_experience(enemy.experience)
        hero.gold += gold
        return Expedition(seed, enemy.name, True, events, enemy.experience, gold,
                          loot, levels, **context)


class Forest(Location):
    code, name, level, loot = "forest", "Мистический лес", 1, ("iron", "bow", "leather")

    def create_enemy(self):
        return Goblin()


class Crypt(Location):
    code, name, level = "crypt", "Заброшенный склеп", 3
    loot = ("knight", "bone", "necro", "crypt")

    def create_enemy(self):
        return Skeleton()


class DragonLair(Location):
    code, name, level, loot = "dragon-lair", "Логово дракона", 5, ("dawn", "dragon")

    def create_enemy(self):
        return Dragon()


class Swamp(Location):
    code, name, level, loot = "swamp", "Туманное болото", 2, ("guardian", "swamp")

    def create_enemy(self):
        return SwampGuardian()


class HauntedManor(Location):
    code, name, level = "manor", "Проклятый особняк", 2
    loot = ("iron", "elven", "ember")

    def create_enemy(self):
        return HauntedWeapon(self.catalog.create(Dice().pick(self.loot)))


LOCATIONS = (Forest, Swamp, HauntedManor, Crypt, DragonLair)


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
