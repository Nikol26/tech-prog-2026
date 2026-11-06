"""Запуск игры: откройте main.py в PyCharm и нажмите Run."""
from heroes import HeroBuilder, KITS
from items import create_catalog
from world import LOCATIONS, DragonLair, Merchant


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
          f"HP {hero.health}/{hero.max_health} | "
          f"опыт {hero.experience}/{hero.level * 100} | золото {hero.gold}")
    print(f"Оружие: {hero.weapon}\nБроня: {hero.armor}")


def show_report(report, location):
    print(f"\n=== {location.name}, сид {report.seed}: {report.enemy} ===")
    for event in report.events:
        critical = " КРИТ!" if event.critical else ""
        print(f"[Раунд {event.round}] {event.source} → {event.target}: "
              f"{event.damage} урона{critical}; осталось HP: {event.health_after}")
        if event.health_after == 0:
            print(f"{event.target} повержен!")
    if report.victory:
        print(f"Победа! +{report.experience} опыта, +{report.gold} золота")
        if report.loot is not None:
            print(f"Добыча: {report.loot}")
        if report.levels:
            print(f"Получено уровней: {report.levels}")
    else:
        print(f"Поражение. Потеряно золота: {-report.gold}. В лагере можно восстановиться.")


def create_hero(catalog):
    while True:
        print("\nСоздание героя")
        options = []
        for kind in KITS:
            kit = kind(catalog)
            options.append(f"{kind.name}, HP {kind.health}: "
                           f"{kit.create_weapon()}, {kit.create_armor()}")
        index = choose(options)
        if index is None:
            continue
        try:
            return (HeroBuilder(catalog).set_name(input("Имя героя: "))
                    .set_class(KITS[index]).build())
        except ValueError as error:
            print(error)


def expedition(hero, catalog):
    locations = [kind(catalog) for kind in LOCATIONS]
    index = choose([f"{loc.name} (рекомендуемый уровень {loc.level})" for loc in locations])
    if index is None:
        return
    raw_seed = input("Сид (целое число; Enter — случайный): ").strip()
    try:
        seed = int(raw_seed) if raw_seed else None
    except ValueError:
        print("Сид должен быть целым числом")
        return
    location = locations[index]
    report = location.explore(hero, seed)
    show_report(report, location)
    if report.victory and isinstance(location, DragonLair):
        print("Дракон побеждён! Главная цель игры выполнена!")


def equipment(hero):
    if not hero.inventory:
        print("Инвентарь пуст")
        return
    index = choose([str(item) for item in hero.inventory])
    if index is not None:
        item = hero.inventory[index]
        hero.equip(item)
        print(f"Экипировано: {item}")


def trade(hero, merchant):
    action = choose(["Купить", "Продать"])
    if action == 0:
        items = [merchant.catalog.create(code) for code in merchant.stock]
        index = choose([f"{item}: {item.price} золота" for item in items])
        if index is not None:
            print(f"Куплено: {merchant.buy(hero, items[index].code)}")
    elif action == 1:
        if not hero.inventory:
            print("Продавать нечего; экипированные предметы не продаются")
            return
        index = choose([f"{item}: {item.price // 2} золота" for item in hero.inventory])
        if index is not None:
            price = merchant.sell(hero, hero.inventory[index])
            print(f"Получено золота: {price}")


def main():
    catalog = create_catalog()
    hero, merchant = create_hero(catalog), Merchant(catalog)
    while True:
        show_hero(hero)
        print("1 — экспедиция, 2 — снаряжение, 3 — торговец, 0 — выход")
        action = input("> ").strip()
        try:
            if action == "0":
                return
            if action == "1":
                expedition(hero, catalog)
            elif action == "2":
                equipment(hero)
            elif action == "3":
                trade(hero, merchant)
            else:
                print("Такого варианта нет")
        except ValueError as error:
            print(error)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nИгра завершена.")
