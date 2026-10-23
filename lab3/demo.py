"""Все пять паттернов одним запуском без ручного ввода."""
from copy import copy, deepcopy
from core import Dice
from heroes import HeroBuilder, KITS, WarriorKit, PaladinKit
from items import create_catalog, FIERY
from main import show_hero, show_report
from world import Forest, Crypt, Swamp, LOCATIONS


def main():
    catalog = create_catalog()
    print("===== 1. Singleton / Одиночка =====")
    print("Dice() is Dice():", Dice() is Dice())
    print("\n===== 2. Prototype / Прототип =====")
    original = catalog.create("iron")
    clone = original.copy()
    clone.enchant(FIERY)
    print("Исходник:", original)
    print("Копия:", clone)
    print("Свежая копия из каталога:", catalog.create("iron"))
    print("Разные объекты:", original is not clone)
    print("Поверхностная копия делит список:", copy(original).enchantments is original.enchantments)
    print("Глубокая копия имеет новый список:", deepcopy(original).enchantments is not original.enchantments)
    print("Наш copy() имеет новый список:", clone.enchantments is not original.enchantments)
    print("\n===== 3. Abstract Factory / Абстрактная фабрика =====")
    for kind in KITS:
        factory = kind(catalog)
        print(f"{kind.name}: {factory.create_weapon()} + {factory.create_armor()}")
    print("\n===== 4. Builder / Строитель =====")
    hero = (HeroBuilder(catalog).set_name("Артур").set_class(WarriorKit)
            .set_level(3).build())
    show_hero(hero)
    for builder in (HeroBuilder(catalog).set_class(WarriorKit),
                    HeroBuilder(catalog).set_name("Мерлин")):
        try:
            builder.build()
        except ValueError as error:
            print("Проверка строителя:", error)
    print("\n===== 5. Factory Method / Фабричный метод =====")
    for kind in LOCATIONS:
        print(f"{kind.__name__}.create_enemy() → {type(kind(catalog).create_enemy()).__name__}")
    for kind in (Forest, Crypt):
        location = kind(catalog)
        show_report(location.explore(hero, 7), location)
    print("\n===== Дополнительное задание: паладин и болото =====")
    paladin = (HeroBuilder(catalog).set_name("Николь").set_class(PaladinKit)
               .set_level(3).build())
    show_hero(paladin)
    location = Swamp(catalog)
    show_report(location.explore(paladin, 7), location)


if __name__ == "__main__":
    main()
