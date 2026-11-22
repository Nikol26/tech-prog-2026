"""Структурные паттерны: Proxy, Decorator и дополнительное задание Adapter."""
from unittest.mock import call, create_autospec, patch
import pytest
from core import Hit
from combat import Damage
from heroes import HeroBuilder, WarriorKit
from items import Weapon
from storage import CachingHeroRepository, HeroRepository
from world import Goblin, LegendaryEnemy, WindfuryEnemy, ArmoredEnemy, HauntedWeapon


@pytest.mark.unit
class TestCachingHeroRepository:
    def storage(self, heroes=()):
        storage = create_autospec(HeroRepository, instance=True)
        storage.find_all.return_value = list(heroes)
        return storage

    def test_does_not_load_until_first_read(self):
        storage = self.storage()
        CachingHeroRepository(storage)
        assert storage.mock_calls == []

    def test_repeated_lookups_and_listing_read_storage_once(self, hero):
        storage = self.storage([hero])
        cache = CachingHeroRepository(storage)
        assert cache.find_by_name("Артур") is hero
        assert cache.find_by_name("Артур") is hero
        assert cache.find_all()[0] is hero
        assert cache.find_by_name("Нет такого героя") is None
        storage.find_all.assert_called_once_with()
        storage.save.assert_not_called()

    def test_empty_storage_is_cached_too(self):
        storage = self.storage()
        cache = CachingHeroRepository(storage)
        assert cache.find_by_name("Никто") is None
        assert cache.find_by_name("Никто") is None
        assert cache.find_all() == []
        storage.find_all.assert_called_once_with()

    def test_returned_list_cannot_clear_internal_cache(self, hero):
        storage = self.storage([hero])
        cache = CachingHeroRepository(storage)
        cache.find_all().clear()
        assert cache.find_by_name(hero.name) is hero
        storage.find_all.assert_called_once_with()

    def test_save_delegates_and_replaces_cached_identity(self, hero, catalog):
        storage = self.storage([hero])
        cache = CachingHeroRepository(storage)
        assert cache.find_by_name(hero.name) is hero
        updated = HeroBuilder(catalog).set_name("Артур").set_class(WarriorKit).set_gold(150).build()
        cache.save(updated)
        storage.save.assert_called_once_with(updated)
        assert cache.find_by_name("Артур") is updated
        assert cache.find_all() == [updated]
        storage.find_all.assert_called_once_with()

    def test_save_before_read_preserves_other_heroes(self, hero, catalog):
        storage = self.storage([hero])
        cache = CachingHeroRepository(storage)
        other = HeroBuilder(catalog).set_name("Николь").set_class(WarriorKit).build()
        cache.save(other)
        assert storage.mock_calls == [call.find_all(), call.save(other)]
        assert cache.find_by_name("Артур") is hero
        assert cache.find_by_name("Николь") is other

    def test_failed_save_does_not_replace_loaded_cache(self, hero, catalog):
        storage = self.storage([hero])
        cache = CachingHeroRepository(storage)
        assert cache.find_by_name(hero.name) is hero
        updated = HeroBuilder(catalog).set_name("Артур").set_class(WarriorKit).set_gold(999).build()
        storage.save.side_effect = OSError("Диск недоступен")
        with pytest.raises(OSError, match="Диск недоступен"):
            cache.save(updated)
        storage.save.assert_called_once_with(updated)
        assert cache.find_by_name(hero.name) is hero
        assert hero.gold == 50

    def test_failed_first_read_is_retried(self, hero):
        storage = self.storage()
        storage.find_all.side_effect = [OSError("Ошибка чтения"), [hero]]
        cache = CachingHeroRepository(storage)
        with pytest.raises(OSError, match="Ошибка чтения"):
            cache.find_all()
        assert cache.find_by_name(hero.name) is hero
        assert storage.find_all.call_count == 2


@pytest.mark.unit
class TestEnemyDecorators:
    def test_nested_decorators_all_contribute_and_reach_base(self):
        base = Goblin()
        wind = WindfuryEnemy(base)
        legendary = LegendaryEnemy(wind)
        armored = ArmoredEnemy(legendary)
        with patch.object(base, "roll_damage", side_effect=[Hit(7), Hit(11, True)]) as attack:
            result = armored.roll_damage()
        assert result == Hit(36, True)  # (7 + 11) * 2
        assert attack.call_args_list == [call(), call()]
        with patch.object(base, "roll_gold_reward", return_value=20) as reward:
            assert armored.roll_gold_reward() == 60  # 20 * 1.5 * 2
        reward.assert_called_once_with()
        assert armored.experience == 120  # 40 * 1.5 * 2
        assert armored.name == "Бронированный Легендарный Неистовый Гоблин"
        assert armored.code == "goblin"
        with patch.object(base, "receive_hit", wraps=base.receive_hit) as receive:
            damage = armored.receive_hit(21)
        receive.assert_called_once_with(11)
        assert damage.amount == 11
        assert armored.health == legendary.health == wind.health == base.health == 39

    def test_multiple_armored_wrappers_each_reduce_damage(self):
        base = Goblin()
        wrapped = ArmoredEnemy(ArmoredEnemy(base))
        assert wrapped.receive_hit(21).amount == 6  # ceil(ceil(21 / 2) / 2)
        assert base.health == 44

    def test_zero_damage_is_not_increased_by_decorators(self):
        wrapped = ArmoredEnemy(LegendaryEnemy(WindfuryEnemy(Goblin())))
        assert wrapped.receive_hit(0) == Damage(0)
        assert wrapped.health == 50


@pytest.mark.unit
class TestHauntedWeaponAdapter:
    def test_attack_is_delegated_to_weapon_without_losing_critical(self):
        weapon = create_autospec(Weapon, instance=True)
        weapon.name, weapon.damage, weapon.price = "Тестовый лук", 14, 90
        weapon.roll_damage.return_value = Hit(28, True)
        adapter = HauntedWeapon(weapon)
        assert adapter.roll_damage() == Hit(28, True)
        weapon.roll_damage.assert_called_once_with()
        assert adapter.weapon is weapon
        assert (adapter.max_health, adapter.experience, adapter.gold) == (70, 45, 45)

    def test_real_weapon_retains_item_behavior_while_adapter_is_enemy(self, catalog):
        weapon = catalog.create("iron")
        adapter = HauntedWeapon(weapon)
        assert adapter.roll_damage() == Hit(17)
        assert adapter.receive_hit(12).amount == 12
        assert adapter.health == 73
        assert weapon.damage == 17
        assert weapon.price == 80
