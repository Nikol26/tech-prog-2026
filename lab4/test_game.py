"""Проверки паттернов, игрового меню и прохождения с первого уровня."""
from pathlib import Path
from tempfile import TemporaryDirectory
from combat import (Damage, EvasionHandler, ArmorHandler, BarrierHandler, Action,
                    BalancedTactic, AggressiveTactic, CautiousTactic, TACTICS)
from storage import FileHeroRepository, CachingHeroRepository
from game import (GameFacade, GameEventPublisher, GameEventType, GameEvent,
                  AchievementTracker, ExpeditionJournal, ACHIEVEMENTS)
from world import (Goblin, Dragon, LegendaryEnemy, ArmoredEnemy, WindfuryEnemy,
                   HauntedWeapon, HauntedManor, Expedition)
import contextlib
import io
import unittest
from unittest.mock import patch
from core import Dice
from heroes import HeroBuilder, KITS, WarriorKit, PaladinKit, MageKit
from items import Armor, Weapon, FIERY, STURDY, SHARP, create_catalog
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
        self.assertEqual(types, ["Goblin", "SwampGuardian", "HauntedWeapon", "Skeleton", "Dragon"])
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
        inputs = ["1", "1", "Николь", "?", "1", "1", "1", "bad", "1", "1", "1", "7",
                  "3", "1", "4", "2", "0", "0"]
        with patch("builtins.input", side_effect=inputs):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                with TemporaryDirectory(dir=Path(__file__).parent) as directory:
                    main(Path(directory) / "heroes.json")
        for expected in ("Такого варианта нет", "Сид должен быть целым числом",
                         "Победа!", "Не хватает золота"):
            self.assertIn(expected, output.getvalue())

    def test_menu_invalid_selection(self):
        for answer in ("x", "0", "-1", "99"):
            with patch("builtins.input", return_value=answer):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(choose(["один"]))




class Lab4Tests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="test-", dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / "heroes.json"
        self.catalog = create_catalog()

    def hero(self, kind=WarriorKit, level=1):
        return HeroBuilder(self.catalog).set_name("Артур").set_class(kind).set_level(level).build()

    def test_chain_order_and_depleting_barrier(self):
        armor = ArmorHandler(0.3)
        barrier = BarrierHandler(30)
        armor.set_next(barrier)
        amounts = []
        for _ in range(3):
            damage = Damage(30)
            armor.handle(damage)
            amounts.append((damage.amount, damage.absorbed))
        self.assertEqual(amounts, [(0, 21), (12, 9), (21, 0)])
        reverse = BarrierHandler(30)
        reverse.set_next(ArmorHandler(0.3))
        damage = Damage(30)
        reverse.handle(damage)
        self.assertEqual(damage.amount, 0)

    def test_evasion_stops_chain_and_preserves_barrier(self):
        first, barrier = EvasionHandler(1), BarrierHandler(30)
        first.set_next(barrier)
        damage = Damage(100)
        first.handle(damage)
        self.assertTrue(damage.evaded)
        self.assertEqual((damage.amount, barrier.remaining), (0, 30))

    def test_zero_and_negative_damage(self):
        for target in (self.hero(), Goblin(), ArmoredEnemy(Goblin()), HauntedWeapon(self.catalog.create("iron"))):
            with self.subTest(target=type(target)):
                health = target.health
                self.assertEqual(target.receive_hit(0).amount, 0)
                self.assertEqual(target.health, health)
                with self.assertRaises(ValueError):
                    target.receive_hit(-1)

    def test_hero_rest_resets_barrier(self):
        mage = self.hero(MageKit)
        self.assertEqual(mage.receive_hit(20).amount, 0)
        mage.receive_hit(20)
        self.assertLess(mage.health, mage.max_health)
        mage.rest()
        self.assertEqual(mage.health, mage.max_health)
        self.assertEqual(mage.receive_hit(20).amount, 0)

    def test_enemy_chain_and_composed_decorators(self):
        base = Goblin()
        wrapped = ArmoredEnemy(LegendaryEnemy(WindfuryEnemy(base)))
        Dice().reseed(5)
        expected = (base.roll_damage().damage + base.roll_damage().damage) * 2
        Dice().reseed(5)
        self.assertEqual(wrapped.roll_damage().damage, expected)
        self.assertEqual(wrapped.experience, 120)
        self.assertEqual(wrapped.code, "goblin")
        self.assertEqual(wrapped.receive_hit(20).amount, 10)
        self.assertEqual((wrapped.health, base.health), (40, 40))
        dragon = Dragon()
        self.assertEqual(dragon.receive_hit(20).absorbed, 15)

    def test_adapter_delegates_weapon_attack(self):
        weapon = self.catalog.create("elven")
        adapter = HauntedWeapon(weapon)
        Dice().reseed(9)
        expected = weapon.roll_damage()
        Dice().reseed(9)
        self.assertEqual(adapter.roll_damage(), expected)
        self.assertEqual(adapter.max_health, weapon.damage * 5)
        self.assertEqual(adapter.experience, weapon.price // 2)
        self.assertIsInstance(HauntedManor(self.catalog).create_enemy(), HauntedWeapon)

    def test_strategy_conditions(self):
        hero, enemy = self.hero(), Dragon()
        self.assertEqual(BalancedTactic().choose_action(1, hero, enemy), Action.ATTACK)
        self.assertEqual(AggressiveTactic().choose_action(1, hero, enemy), Action.POWER_STRIKE)
        hero.health = 20
        self.assertEqual(CautiousTactic().choose_action(2, hero, enemy), Action.DEFEND)
        self.assertEqual(CautiousTactic().choose_action(3, hero, enemy), Action.ATTACK)

    def test_strategies_produce_different_battles(self):
        reports = [Crypt(self.catalog).explore(self.hero(MageKit, 2), 9, tactic) for tactic in TACTICS]
        self.assertEqual({event.action for event in reports[0].events}, {"ATTACK"})
        self.assertIn("POWER_STRIKE", {event.action for event in reports[1].events})
        self.assertIn("DEFEND", {event.action for event in reports[2].events})
        self.assertNotEqual(reports[0].events, reports[1].events)

    def test_random_elites_and_seed_replay(self):
        reports = [Forest(self.catalog).explore(self.hero(level=5), seed) for seed in range(40)]
        self.assertTrue(any("Легендарный" in r.enemy or "Неистовый" in r.enemy for r in reports))
        self.assertTrue(any(r.enemy == "Гоблин" for r in reports))
        first = Forest(self.catalog).explore(self.hero(level=5), 1)
        second = Forest(self.catalog).explore(self.hero(level=5), 1)
        self.assertEqual(first.events, second.events)
        self.assertEqual(first.enemy, second.enemy)

    def test_repository_roundtrip_full_state_and_multiple_heroes(self):
        hero = self.hero(MageKit, 5)
        hero.gold, hero.experience = 777, 123
        hero.weapon.enchant(FIERY)
        hero.inventory.append(self.catalog.create("plate"))
        hero.inventory.append(self.catalog.create("iron"))
        hero.inventory[-1].enchant(SHARP)
        hero.achievements.update({"first-blood", "lucky", "veteran"})
        repo = FileHeroRepository(self.file, self.catalog)
        repo.save(hero)
        repo.save(HeroBuilder(self.catalog).set_name("Другой").set_class(PaladinKit).build())
        restored = repo.find_by_name(hero.name)
        self.assertIsNot(hero, restored)
        self.assertEqual((restored.gold, restored.level, restored.experience), (777, 5, 123))
        self.assertEqual(restored.weapon.enchantments, [FIERY])
        self.assertEqual(restored.inventory[-1].enchantments, [SHARP])
        self.assertEqual(restored.achievements, hero.achievements)
        self.assertEqual(len(repo.find_all()), 2)
        restored.inventory[-1].enchant(FIERY)
        self.assertEqual(repo.find_by_name(hero.name).inventory[-1].enchantments, [SHARP])

    def test_proxy_identity_and_read_count(self):
        real = FileHeroRepository(self.file, self.catalog)
        real.save(self.hero())
        self.assertIsNot(real.find_by_name("Артур"), real.find_by_name("Артур"))
        cache = CachingHeroRepository(real)
        before = real.reads
        first = cache.find_by_name("Артур")
        self.assertIs(first, cache.find_by_name("Артур"))
        self.assertIs(first, cache.find_all()[0])
        self.assertEqual(real.reads - before, 1)
        first.gold = 123
        cache.save(first)
        self.assertEqual(real.find_by_name("Артур").gold, 123)

    def test_corrupted_file_is_not_overwritten(self):
        for data in ("not json", "{}", '[{"name":"Артур"}]'):
            self.file.write_text(data, encoding="utf-8")
            repo = FileHeroRepository(self.file, self.catalog)
            with self.assertRaises(ValueError):
                repo.save(self.hero())
            self.assertEqual(self.file.read_text(encoding="utf-8"), data)

    def test_failed_atomic_write_preserves_original(self):
        repo = FileHeroRepository(self.file, self.catalog)
        repo.save(self.hero())
        old = self.file.read_bytes()
        hero = self.hero()
        hero.gold = 999
        with patch("storage.os.replace", side_effect=OSError("Запись запрещена")):
            with self.assertRaises(OSError):
                repo.save(hero)
        self.assertEqual(self.file.read_bytes(), old)
        self.assertFalse(list(self.file.parent.glob("*.tmp")))

    def test_observer_achievements_and_journal(self):
        publisher, tracker, journal = GameEventPublisher(), AchievementTracker(), ExpeditionJournal()
        for event_type in (GameEventType.VICTORY, GameEventType.LEVEL_UP):
            publisher.subscribe(event_type, tracker)
        publisher.subscribe(GameEventType.VICTORY, journal)
        hero = self.hero(level=5)
        loot = self.catalog.create("iron")
        loot.enchant(FIERY)
        report = Expedition(7, "Легендарный Дракон", True, (), loot=loot, enemy_code="dragon")
        publisher.publish(GameEvent(GameEventType.VICTORY, hero, report))
        publisher.publish(GameEvent(GameEventType.LEVEL_UP, hero, report))
        self.assertEqual(hero.achievements, set(ACHIEVEMENTS))
        self.assertEqual(journal.get_entries(hero.name), (report,))
        publisher.unsubscribe(GameEventType.VICTORY, journal)
        publisher.publish(GameEvent(GameEventType.VICTORY, hero, report))
        self.assertEqual(len(journal.get_entries(hero.name)), 1)
        self.assertEqual(len(hero.achievements), 4)

    def test_facade_saves_and_restores_victory_and_defeat(self):
        game = GameFacade(self.file)
        game.create_hero("  Артур  ", "warrior")
        with self.assertRaises(ValueError):
            game.create_hero("Артур", "warrior")
        victory = game.explore("Артур", "forest", "balanced", seed=7)
        self.assertTrue(victory.victory)
        self.assertIn("first-blood", GameFacade(self.file).get_hero("Артур").achievements)
        defeat = game.explore("Артур", "dragon-lair", "balanced", seed=7)
        self.assertFalse(defeat.victory)
        self.assertEqual(len(game.get_journal("Артур")), 2)
        self.assertEqual(GameFacade(self.file).get_hero("Артур").gold, game.get_hero("Артур").gold)
        self.assertEqual(GameFacade(self.file).get_journal("Артур"), ())

    def test_facade_trading_and_equipment_persist(self):
        game = GameFacade(self.file)
        hero = game.create_hero("Артур", "warrior")
        hero.gold = 500
        game.save(hero.name)
        item = game.buy(hero.name, "iron")
        game.equip(hero.name, hero.inventory.index(item))
        game.sell(hero.name, 0)
        loaded = GameFacade(self.file).get_hero(hero.name)
        self.assertEqual(loaded.weapon.code, "iron")
        self.assertEqual(loaded.gold, 430)
        self.assertEqual(loaded.inventory, [])

    def test_bad_facade_codes_do_not_mutate_hero(self):
        game = GameFacade(self.file)
        hero = game.create_hero("Артур", "warrior")
        for location, tactic in (("missing", "balanced"), ("forest", "missing")):
            with self.assertRaises(ValueError):
                game.explore(hero.name, location, tactic, 7)
        with self.assertRaises(ValueError):
            game.equip(hero.name, -1)
        self.assertEqual((hero.gold, hero.experience), (50, 0))

    def test_cli_reloads_same_hero(self):
        with patch("builtins.input", side_effect=["1", "1", "Николь", "1", "1", "1", "7", "4", "5", "0"]):
            with contextlib.redirect_stdout(io.StringIO()) as first:
                main(self.file)
        self.assertIn("Победа!", first.getvalue())
        self.assertIn("Новое достижение: Первая кровь", first.getvalue())
        with patch("builtins.input", side_effect=["2", "1", "0"]):
            with contextlib.redirect_stdout(io.StringIO()) as second:
                main(self.file)
        self.assertIn("Первая кровь", second.getvalue())
        self.assertNotIn("Имя героя:", second.getvalue())

    def test_campaign_through_facade_survives_restarts(self):
        game = GameFacade(self.file)
        for kind in KITS:
            name = kind.code
            game.create_hero(name, kind.code)
            won = False
            for seed in range(200):
                hero = game.get_hero(name)
                code = "forest" if hero.level < 3 else "crypt" if hero.level < 8 else "dragon-lair"
                report = game.explore(name, code, "balanced", seed)
                # Все действия идут через фасад, а не напрямую меняют снаряжение.
                index = 0
                while index < len(hero.inventory):
                    item = hero.inventory[index]
                    if isinstance(item, Weapon) and item.damage > hero.weapon.damage:
                        game.equip(name, index)
                    elif isinstance(item, Armor) and item.defense > hero.armor.defense:
                        game.equip(name, index)
                    else:
                        index += 1
                if seed % 15 == 0:
                    game = GameFacade(self.file)
                if code == "dragon-lair" and report.victory:
                    won = True
                    break
            self.assertTrue(won, kind.code)
            loaded = GameFacade(self.file).get_hero(name)
            self.assertIn("dragon-slayer", loaded.achievements)
            self.assertIn("veteran", loaded.achievements)


if __name__ == "__main__":
    unittest.main()
