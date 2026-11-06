"""Лабораторная №4. Откройте main.py в PyCharm и нажмите Run."""
from pathlib import Path
from game import GameFacade, ACHIEVEMENTS
from combat import Action

SAVE_FILE = Path(__file__).with_name("heroes.json")


def choose(options, prompt="Выберите номер (0 — назад):"):
    for number, text in enumerate(options, 1):
        print(f"{number} — {text}")
    try:
        number = int(input(prompt + " ").strip())
        if 1 <= number <= len(options):
            return number - 1
    except ValueError:
        pass
    return None


def show_hero(hero):
    print(f"\n{hero.name}, {hero.hero_class.name}, уровень {hero.level} | "
          f"HP {hero.health}/{hero.max_health} | опыт {hero.experience}/{hero.level * 100} | "
          f"золото {hero.gold}\nОружие: {hero.weapon}\nБроня: {hero.armor}")
    names = [ACHIEVEMENTS[code][0] for code in sorted(hero.achievements)]
    print("Достижения: " + (", ".join(names) if names else "пока нет"))


def show_report(report, location):
    print(f"\n=== {location.name}, тактика {report.tactic_code}, сид {report.seed} ===")
    print("Противник: " + report.enemy)
    for event in report.events:
        if event.action != "ATTACK" and event.source != report.enemy:
            print(f"[Раунд {event.round}] {Action[event.action].title}")
        if event.evaded:
            print(f"{event.target} уклоняется от удара")
        else:
            extra = f", барьер поглотил {event.absorbed}" if event.absorbed else ""
            critical = " КРИТ!" if event.critical else ""
            print(f"[Раунд {event.round}] {event.source} → {event.target}: "
                  f"{event.damage} урона{critical}{extra}; HP: {event.health_after}")
        if event.health_after == 0:
            print(f"{event.target} повержен!")
    if report.victory:
        print(f"Победа! +{report.experience} опыта, +{report.gold} золота")
        if report.loot is not None:
            print(f"Добыча: {report.loot}")
        if report.levels:
            print(f"Получено уровней: {report.levels}")
        if report.enemy_code == "dragon":
            print("Дракон побеждён! Главная цель игры выполнена!")
    else:
        print(f"Поражение. Потеряно золота: {-report.gold}. Перед экспедицией герой отдохнёт.")


def choose_hero(game):
    while True:
        print("\n1 — создать героя, 2 — продолжить сохранённую игру, 0 — выход")
        action = input("> ").strip()
        if action == "0":
            return None
        if action == "2":
            heroes = game.heroes
            if not heroes:
                print("Сохранённых героев пока нет")
                continue
            index = choose([f"{hero.name}: {hero.hero_class.name}, ур. {hero.level}" for hero in heroes])
            if index is not None:
                return heroes[index].name
        elif action == "1":
            options = []
            for kind in game.hero_classes:
                kit = kind(game.catalog)
                options.append(f"{kind.name}, HP {kind.health}: "
                               f"{kit.create_weapon()}, {kit.create_armor()}")
            index = choose(options)
            if index is None:
                continue
            try:
                hero = game.create_hero(input("Имя героя: "), game.hero_classes[index].code)
                return hero.name
            except ValueError as error:
                print(error)
        else:
            print("Такого варианта нет")


def expedition(game, name):
    index = choose([f"{loc.name} (рекомендуемый уровень {loc.level})" for loc in game.locations])
    if index is None:
        return
    location = game.locations[index]
    index = choose([f"{t.name}: {t.description}" for t in game.tactics])
    if index is None:
        return
    tactic = game.tactics[index]
    raw_seed = input("Сид (целое число; Enter — случайный): ").strip()
    try:
        seed = int(raw_seed) if raw_seed else None
    except ValueError:
        print("Сид должен быть целым числом")
        return
    before = game.get_hero(name).achievements.copy()
    report = game.explore(name, location.code, tactic.code, seed)
    show_report(report, location)
    for code in sorted(game.get_hero(name).achievements - before):
        print("Новое достижение: " + ACHIEVEMENTS[code][0])


def equipment(game, name):
    inventory = game.get_hero(name).inventory
    if not inventory:
        print("Инвентарь пуст")
        return
    index = choose([str(item) for item in inventory])
    if index is not None:
        print(f"Экипировано: {game.equip(name, index)}")


def trade(game, name):
    action = choose(["Купить", "Продать"])
    if action == 0:
        items = game.showcase
        index = choose([f"{item}: {item.price} золота" for item in items])
        if index is not None:
            print(f"Куплено: {game.buy(name, items[index].code)}")
    elif action == 1:
        inventory = game.get_hero(name).inventory
        if not inventory:
            print("Продавать нечего; экипированные предметы не продаются")
            return
        index = choose([f"{item}: {item.price // 2} золота" for item in inventory])
        if index is not None:
            print(f"Получено золота: {game.sell(name, index)}")


def show_journal(game, name):
    reports = game.get_journal(name)
    if not reports:
        print("В этом запуске экспедиций ещё не было")
    for number, report in enumerate(reports, 1):
        outcome = "победа" if report.victory else "поражение"
        print(f"{number}. {report.location_code}, {report.enemy}, {report.tactic_code}: "
              f"{outcome}, сид {report.seed}")


def main(save_file=None):
    game = GameFacade(SAVE_FILE if save_file is None else save_file)
    try:
        name = choose_hero(game)
        if name is None:
            return
        while True:
            show_hero(game.get_hero(name))
            print("1 — экспедиция, 2 — снаряжение, 3 — торговец, "
                  "4 — журнал, 5 — достижения, 6 — сохранить, 0 — сохранить и выйти")
            action = input("> ").strip()
            try:
                if action == "0":
                    game.save(name)
                    print("Игра сохранена.")
                    return
                if action == "1":
                    expedition(game, name)
                elif action == "2":
                    equipment(game, name)
                elif action == "3":
                    trade(game, name)
                elif action == "4":
                    show_journal(game, name)
                elif action == "5":
                    unlocked = game.get_hero(name).achievements
                    for code, (title, description) in ACHIEVEMENTS.items():
                        print(f"{'[+]' if code in unlocked else '[ ]'} {title}: {description}")
                elif action == "6":
                    game.save(name)
                    print("Игра сохранена.")
                else:
                    print("Такого варианта нет")
            except ValueError as error:
                print(error)
    except (OSError, ValueError) as error:
        print(f"Не удалось работать с сохранением: {error}")
        print("Существующий файл не очищен. Проверьте heroes.json и права доступа.")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nИгра завершена. Завершённые действия сохранены автоматически.")
