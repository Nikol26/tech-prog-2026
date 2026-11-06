"""Демонстрация всех семи паттернов лабы 4; пользовательские сохранения не меняются."""
from pathlib import Path
from tempfile import TemporaryDirectory
from core import Dice
from combat import (Damage, ArmorHandler, BarrierHandler, EvasionHandler, TACTICS)
from heroes import HeroBuilder, WarriorKit, MageKit
from items import create_catalog
from world import (Goblin, Dragon, LegendaryEnemy, WindfuryEnemy, ArmoredEnemy,
                   HauntedWeapon, HauntedManor, Forest, Crypt)
from storage import FileHeroRepository, CachingHeroRepository
from game import (GameFacade, GameEventPublisher, GameEvent, GameEventType,
                  AchievementTracker, ExpeditionJournal, ACHIEVEMENTS)
from main import show_report


def hero(catalog, name="Артур", kind=WarriorKit, level=3):
    return HeroBuilder(catalog).set_name(name).set_class(kind).set_level(level).build()


def show_chain(title, chain):
    results = []
    for _ in range(3):
        damage = Damage(30)
        chain.handle(damage)
        results.append(f"прошло {damage.amount}, поглощено {damage.absorbed}, уклонение {damage.evaded}")
    print(title + ": " + "; ".join(results))


def main():
    catalog = create_catalog()
    print("===== 1. Chain of Responsibility / Цепочка обязанностей =====")
    show_chain("Только броня 30%", ArmorHandler(0.3))
    armor = ArmorHandler(0.3)
    armor.set_next(BarrierHandler(30))
    show_chain("Броня -> барьер", armor)
    evasion = EvasionHandler(0.5)
    evasion.set_next(ArmorHandler(0.3)).set_next(BarrierHandler(30))
    Dice().reseed(3)
    show_chain("Уклонение -> броня -> барьер", evasion)

    print("\n===== 2. Strategy / Стратегия =====")
    for tactic in TACTICS:
        mage = hero(catalog, "Мерлин", MageKit, 2)
        report = Crypt(catalog).explore(mage, seed=9, tactic=tactic)
        actions = sorted({event.action for event in report.events})
        print(f"{tactic.name}: {'победа' if report.victory else 'поражение'}, "
              f"раундов {report.events[-1].round}, HP {mage.health}; действия {actions}")

    print("\n===== 3. Decorator / Декоратор =====")
    enemies = (Goblin(), LegendaryEnemy(Goblin()), WindfuryEnemy(Goblin()),
               LegendaryEnemy(WindfuryEnemy(Goblin())), ArmoredEnemy(Goblin()),
               ArmoredEnemy(LegendaryEnemy(WindfuryEnemy(Dragon()))))
    for enemy in enemies:
        Dice().reseed(5)
        hits = [enemy.roll_damage().damage for _ in range(3)]
        damage = enemy.receive_hit(20)
        print(f"{enemy.name}: удары {hits}, опыт {enemy.experience}; "
              f"входящий 20 -> {damage.amount}, барьер {damage.absorbed}; HP {enemy.health}")

    print("\n===== 4. Adapter / Адаптер =====")
    weapon = catalog.create("elven")
    enemy = HauntedWeapon(weapon)
    print(f"Предмет: {weapon}; враг: {enemy.name}, HP {enemy.max_health}")
    print("Атакует через тот же предмет:", enemy.weapon is weapon)
    manor = HauntedManor(catalog)
    show_report(manor.explore(hero(catalog), seed=55), manor)

    print("\n===== 5. Observer / Наблюдатель =====")
    publisher = GameEventPublisher()
    journal, tracker = ExpeditionJournal(), AchievementTracker()
    publisher.subscribe(GameEventType.VICTORY, tracker)
    publisher.subscribe(GameEventType.LEVEL_UP, tracker)
    publisher.subscribe(GameEventType.VICTORY, journal)
    warrior = (HeroBuilder(catalog).set_name("Артур").set_class(WarriorKit)
               .set_level(4).set_experience(399).build())
    report = Forest(catalog).explore(warrior, seed=7)
    publisher.publish(GameEvent(GameEventType.VICTORY, warrior, report))
    publisher.publish(GameEvent(GameEventType.LEVEL_UP, warrior, report))
    print("Два независимых подписчика обработали одну экспедицию.")
    print("Достижения:", [ACHIEVEMENTS[code][0] for code in sorted(warrior.achievements)])
    print("Записей в журнале:", len(journal.get_entries(warrior.name)))

    with TemporaryDirectory(prefix="demo-", dir=Path(__file__).parent) as temporary:
        print("\n===== 6. Proxy / Заместитель =====")
        repository = FileHeroRepository(Path(temporary) / "heroes.json", catalog)
        repository.save(warrior)
        print("Без кэша один объект:", repository.find_by_name("Артур") is repository.find_by_name("Артур"))
        cache = CachingHeroRepository(repository)
        reads = repository.reads
        first, second = cache.find_by_name("Артур"), cache.find_by_name("Артур")
        print("Через Proxy один объект:", first is second)
        print("Обращений к файлу за два поиска:", repository.reads - reads)
        first.gold += 100
        cache.save(first)
        print("Золото записано в файл:", repository.find_by_name("Артур").gold)

        print("\n===== 7. Facade / Фасад =====")
        file = Path(temporary) / "game.json"
        game = GameFacade(file)
        game.create_hero("Гэндальф", "mage")
        report = game.explore("Гэндальф", "forest", "cautious", seed=7)
        print("Один вызов фасада: бой -> награды -> события -> сохранение.")
        print("Победа:", report.victory, "; журнал:", len(game.get_journal("Гэндальф")))
        restored = GameFacade(file).get_hero("Гэндальф")
        print("Новый фасад загрузил героя:", restored.name, "; золото:", restored.gold)
        print("Достижения восстановлены:", sorted(restored.achievements))


if __name__ == "__main__":
    main()
