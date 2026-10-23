"""Проверки паттернов, игрового меню и прохождения с первого уровня."""
import contextlib
import io
import unittest
from unittest.mock import patch
from core import Dice
from heroes import HeroBuilder, KITS, WarriorKit, PaladinKit
from items import Armor, Weapon, FIERY, STURDY, create_catalog
from main import main, choose
from world import LOCATIONS, Forest, Crypt, DragonLair, Swamp, Merchant


class GameTests(unittest.TestCase):
    def setUp(self):
        self.catalog = create_catalog()

    def builder(self, kind=WarriorKit):
        return HeroBuilder(self.catalog).set_name("Артур").set_class(kind)

    def test_singleton_and_seed(self):
        first, second = Dice(), Dice()
        self.assertIs(first, second)
        first.reseed(42)
        expected = [second.roll(1, 100) for _ in range(10)]
        second.reseed(42)
        self.assertEqual(expected, [first.roll(1, 100) for _ in range(10)])

    def test_prototype_independence(self):
        original = self.catalog.create("iron")
        clone = original.copy()
        clone.enchant(FIERY)
        self.assertIsNot(original, clone)
        self.assertEqual(original.enchantments, [])
        self.assertEqual(self.catalog.create("iron").enchantments, [])
        self.assertEqual(clone.damage, original.damage + 6)
        self.assertEqual(clone.price, original.price + 50)

    def test_catalog_does_not_share_registered_item(self):
        item = self.catalog.create("iron")
        self.catalog.register(item)
        item.enchant(FIERY)
        self.assertEqual(self.catalog.create("iron").enchantments, [])

    def test_invalid_item_and_enchantment(self):
        with self.assertRaises(ValueError):
            self.catalog.create("missing")
        with self.assertRaises(ValueError):
            self.catalog.create("iron").enchant(STURDY)

    def test_four_abstract_factory_families(self):
        pairs = set()
        for kind in KITS:
            kit = kind(self.catalog)
            weapon, armor = kit.create_weapon(), kit.create_armor()
            self.assertIsInstance(weapon, Weapon)
            self.assertIsInstance(armor, Armor)
            self.assertIsNot(weapon, kit.create_weapon())
            pairs.add((weapon.code, armor.code))
        self.assertEqual(len(pairs), 4)

    def test_builder_defaults_and_independent_heroes(self):
        builder = self.builder().set_level(3)
        first, second = builder.build(), builder.build()
        self.assertEqual((first.level, first.health, first.gold), (3, 150, 50))
        first.weapon.enchant(FIERY)
        self.assertEqual(second.weapon.enchantments, [])

    def test_builder_validation(self):
        builders = [HeroBuilder(self.catalog), HeroBuilder(self.catalog).set_name("А"),
                    self.builder().set_name(" "), self.builder().set_name("а" * 21),
                    self.builder().set_level(0), self.builder().set_gold(-1)]
        for builder in builders:
            with self.subTest(builder=builder):
                with self.assertRaises(ValueError):
                    builder.build()

    def test_factory_method_enemy_types(self):
        types = [type(kind(self.catalog).create_enemy()).__name__ for kind in LOCATIONS]
        self.assertEqual(types, ["Goblin", "SwampGuardian", "Skeleton", "Dragon"])
        location = Forest(self.catalog)
        self.assertIsNot(location.create_enemy(), location.create_enemy())

    def test_expedition_replay_same_starting_state(self):
        first = Forest(self.catalog).explore(self.builder().build(), 7)
        second = Forest(self.catalog).explore(self.builder().build(), 7)
        self.assertEqual(first.events, second.events)
        self.assertEqual((first.victory, first.gold, first.experience),
                         (second.victory, second.gold, second.experience))
        self.assertEqual(str(first.loot), str(second.loot))

    def test_defeat_and_rest(self):
        hero = self.builder().set_gold(51).build()
        report = DragonLair(self.catalog).explore(hero, 7)
        self.assertFalse(report.victory)
        self.assertEqual((hero.gold, report.gold, hero.experience), (26, -25, 0))
        self.assertTrue(Forest(self.catalog).explore(hero, 7).victory)

    def test_level_progression(self):
        hero = self.builder().build()
        self.assertEqual(hero.gain_experience(650), 3)
        self.assertEqual((hero.level, hero.experience), (4, 50))
        with self.assertRaises(ValueError):
            hero.gain_experience(-1)

    def test_buy_equip_sell(self):
        hero = self.builder().set_gold(200).build()
        merchant = Merchant(self.catalog)
        item = merchant.buy(hero, "iron")
        old = hero.weapon
        hero.equip(item)
        self.assertIs(hero.weapon, item)
        self.assertIn(old, hero.inventory)
        self.assertEqual(merchant.sell(hero, old), 10)
        self.assertEqual(hero.gold, 130)
        with self.assertRaises(ValueError):
            merchant.sell(hero, item)

    def test_bad_transactions_preserve_state(self):
        hero = self.builder().set_gold(0).build()
        merchant = Merchant(self.catalog)
        for code in ("iron", "missing"):
            with self.assertRaises(ValueError):
                merchant.buy(hero, code)
        with self.assertRaises(ValueError):
            hero.spend_gold(-1)
        self.assertEqual((hero.gold, hero.inventory), (0, []))

    def test_bonus_loot_and_armor_limit(self):
        hero = self.builder(PaladinKit).set_level(5).build()
        loot = {report.loot.code for seed in range(50)
                if (report := Swamp(self.catalog).explore(hero, seed)).loot is not None}
        self.assertEqual(loot, {"guardian", "swamp"})
        for _ in range(30):
            hero.armor.enchant(STURDY)
        self.assertEqual(hero.armor.defense, 80)

    def test_campaign_all_classes_from_level_one(self):
        for kind in KITS:
            with self.subTest(kind=kind.name):
                hero = self.builder(kind).build()
                won = False
                for seed in range(200):
                    location = (Forest if hero.level < 3 else
                                Crypt if hero.level < 7 else DragonLair)(self.catalog)
                    report = location.explore(hero, seed)
                    for item in tuple(hero.inventory):
                        if isinstance(item, Weapon) and item.damage > hero.weapon.damage:
                            hero.equip(item)
                        elif isinstance(item, Armor) and item.defense > hero.armor.defense:
                            hero.equip(item)
                    if isinstance(location, DragonLair) and report.victory:
                        won = True
                        break
                self.assertTrue(won)

    def test_cli_route_invalid_seed_combat_and_shop(self):
        inputs = ["1", "Николь", "?", "1", "1", "bad", "1", "1", "7",
                  "3", "1", "4", "2", "0"]
        with patch("builtins.input", side_effect=inputs):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                main()
        for expected in ("Такого варианта нет", "Сид должен быть целым числом",
                         "Победа!", "Не хватает золота"):
            self.assertIn(expected, output.getvalue())

    def test_menu_invalid_selection(self):
        for answer in ("x", "0", "-1", "99"):
            with patch("builtins.input", return_value=answer):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(choose(["один"]))


if __name__ == "__main__":
    unittest.main()
