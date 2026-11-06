"""Observer и Facade: события, достижения и единая точка управления игрой."""
from dataclasses import dataclass
from enum import Enum
from heroes import HeroBuilder, KITS
from items import create_catalog
from world import LOCATIONS, Merchant
from combat import TACTICS
from storage import FileHeroRepository, CachingHeroRepository

ACHIEVEMENTS = {
    "first-blood": ("Первая кровь", "Одержать первую победу"),
    "lucky": ("Счастливчик", "Найти зачарованную добычу"),
    "veteran": ("Ветеран", "Достичь пятого уровня"),
    "dragon-slayer": ("Драконоборец", "Победить дракона"),
}


class GameEventType(Enum):
    VICTORY = "victory"
    DEFEAT = "defeat"
    LEVEL_UP = "level-up"


@dataclass(frozen=True)
class GameEvent:
    type: GameEventType
    hero: object
    expedition: object


class GameEventPublisher:
    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_type, listener):
        listeners = self.listeners.setdefault(event_type, [])
        if listener not in listeners:
            listeners.append(listener)

    def unsubscribe(self, event_type, listener):
        listeners = self.listeners.get(event_type, [])
        if listener in listeners:
            listeners.remove(listener)

    def publish(self, event):
        # Подписчик может отписаться во время обработки текущего события.
        for listener in tuple(self.listeners.get(event.type, ())):
            listener.on_event(event)


class AchievementTracker:
    def on_event(self, event):
        hero, report = event.hero, event.expedition
        if event.type == GameEventType.VICTORY:
            hero.achievements.add("first-blood")
            if report.enemy_code == "dragon":
                hero.achievements.add("dragon-slayer")
            if report.loot is not None and report.loot.enchantments:
                hero.achievements.add("lucky")
        if event.type == GameEventType.LEVEL_UP and hero.level >= 5:
            hero.achievements.add("veteran")


class ExpeditionJournal:
    def __init__(self):
        self.entries = {}

    def on_event(self, event):
        self.entries.setdefault(event.hero.name, []).append(event.expedition)

    def get_entries(self, name):
        return tuple(self.entries.get(name, ()))


class GameFacade:
    def __init__(self, save_file):
        self.catalog = create_catalog()
        self.locations = tuple(kind(self.catalog) for kind in LOCATIONS)
        self.tactics, self.hero_classes = TACTICS, KITS
        self.merchant = Merchant(self.catalog)
        self.repository = CachingHeroRepository(FileHeroRepository(save_file, self.catalog))
        self.events, self.journal = GameEventPublisher(), ExpeditionJournal()
        tracker = AchievementTracker()
        self.events.subscribe(GameEventType.VICTORY, tracker)
        self.events.subscribe(GameEventType.LEVEL_UP, tracker)
        self.events.subscribe(GameEventType.VICTORY, self.journal)
        self.events.subscribe(GameEventType.DEFEAT, self.journal)

    @property
    def heroes(self):
        return self.repository.find_all()

    @property
    def showcase(self):
        return [self.catalog.create(code) for code in self.merchant.stock]

    def get_hero(self, name):
        hero = self.repository.find_by_name(name)
        if hero is None:
            raise ValueError(f"Герой '{name}' не найден")
        return hero

    def create_hero(self, name, class_code):
        name = name.strip()
        if self.repository.find_by_name(name) is not None:
            raise ValueError("Герой с таким именем уже существует")
        kind = self._by_code(self.hero_classes, class_code, "класс героя")
        hero = HeroBuilder(self.catalog).set_name(name).set_class(kind).build()
        self.repository.save(hero)
        return hero

    @staticmethod
    def _by_code(options, code, what):
        value = next((value for value in options if value.code == code), None)
        if value is None:
            raise ValueError(f"Неизвестный {what}: {code}")
        return value

    def explore(self, name, location_code, tactic_code, seed=None):
        hero = self.get_hero(name)
        location = self._by_code(self.locations, location_code, "код локации")
        tactic = self._by_code(self.tactics, tactic_code, "код тактики")
        report = location.explore(hero, seed=seed, tactic=tactic)
        result = GameEventType.VICTORY if report.victory else GameEventType.DEFEAT
        self.events.publish(GameEvent(result, hero, report))
        if report.levels:
            self.events.publish(GameEvent(GameEventType.LEVEL_UP, hero, report))
        self.repository.save(hero)
        return report

    @staticmethod
    def _inventory_item(hero, index):
        if type(index) is not int or not 0 <= index < len(hero.inventory):
            raise ValueError("Некорректный номер предмета")
        return hero.inventory[index]

    def equip(self, name, index):
        hero = self.get_hero(name)
        item = self._inventory_item(hero, index)
        hero.equip(item)
        self.repository.save(hero)
        return item

    def buy(self, name, code):
        hero = self.get_hero(name)
        item = self.merchant.buy(hero, code)
        self.repository.save(hero)
        return item

    def sell(self, name, index):
        hero = self.get_hero(name)
        item = self._inventory_item(hero, index)
        price = self.merchant.sell(hero, item)
        self.repository.save(hero)
        return price

    def save(self, name):
        self.repository.save(self.get_hero(name))

    def get_journal(self, name):
        self.get_hero(name)
        return self.journal.get_entries(name)
