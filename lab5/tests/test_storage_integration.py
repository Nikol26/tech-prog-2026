"""Интеграционные тесты настоящего JSON-репозитория и файловой системы."""
from unittest.mock import patch
import pytest
from heroes import HeroBuilder, KITS, PaladinKit
from items import create_catalog, FIERY, STURDY, SHARP
from storage import FileHeroRepository, CachingHeroRepository


@pytest.mark.integration
class TestFileHeroRepository:
    def test_missing_file_means_empty_storage(self, tmp_path, catalog):
        file = tmp_path / "missing.json"
        repository = FileHeroRepository(file, catalog)
        assert repository.find_all() == []
        assert repository.find_by_name("Артур") is None
        assert not file.exists()

    @pytest.mark.parametrize("kind", KITS, ids=lambda kind: kind.code)
    def test_new_repository_restores_full_hero_state(self, tmp_path, catalog, kind):
        file = tmp_path / "nested" / "heroes.json"
        original = (HeroBuilder(catalog).set_name("Николь").set_class(kind)
                    .set_level(5).set_experience(123).set_gold(777)
                    .set_achievements({"first-blood", "lucky", "veteran"}).build())
        original.weapon.enchant(FIERY)
        original.armor.enchant(STURDY)
        item = catalog.create("iron")
        item.enchant(SHARP)
        original.inventory.append(item)
        original.health = 1  # По контракту здоровье не сохраняется: герой отдыхает при загрузке.

        FileHeroRepository(file, catalog).save(original)
        restored = FileHeroRepository(file, create_catalog()).find_by_name("Николь")

        assert restored is not None and restored is not original
        assert (restored.name, restored.hero_class, restored.level, restored.experience,
                restored.gold) == ("Николь", kind, 5, 123, 777)
        assert restored.weapon.code == original.weapon.code
        assert restored.armor.code == original.armor.code
        assert restored.weapon.enchantments == [FIERY]
        assert restored.armor.enchantments == [STURDY]
        assert [(item.code, item.enchantments) for item in restored.inventory] == [("iron", [SHARP])]
        assert restored.achievements == {"first-blood", "lucky", "veteran"}
        assert restored.health == restored.max_health

    def test_saving_same_name_updates_without_duplicate_and_keeps_others(self, tmp_path, catalog, hero):
        file = tmp_path / "heroes.json"
        repository = FileHeroRepository(file, catalog)
        other = HeroBuilder(catalog).set_name("Мария").set_class(PaladinKit).build()
        repository.save(hero)
        repository.save(other)
        hero.gold = 175
        repository.save(hero)
        loaded = FileHeroRepository(file, create_catalog()).find_all()
        assert {hero.name: hero.gold for hero in loaded} == {"Артур": 175, "Мария": 50}

    def test_each_read_restores_independent_objects(self, tmp_path, catalog, hero):
        repository = FileHeroRepository(tmp_path / "heroes.json", catalog)
        repository.save(hero)
        first = repository.find_by_name("Артур")
        second = repository.find_by_name("Артур")
        assert first is not second
        first.weapon.enchant(FIERY)
        assert second.weapon.enchantments == []
        assert repository.find_by_name("Артур").weapon.enchantments == []

    @pytest.mark.parametrize("invalid", [
        "not json", "{}", '[{"name":"Артур"}]',
        '[{"name":"Артур"},{"name":"Артур"}]'
    ])
    def test_corrupt_save_is_reported_and_never_overwritten(self, tmp_path, catalog, hero, invalid):
        file = tmp_path / "heroes.json"
        file.write_text(invalid, encoding="utf-8")
        before = file.read_bytes()
        repository = FileHeroRepository(file, catalog)
        with pytest.raises(ValueError):
            repository.find_all()
        with pytest.raises(ValueError):
            repository.save(hero)
        assert file.read_bytes() == before

    def test_atomic_write_failure_preserves_original_and_removes_temporary_file(self, tmp_path, catalog, hero):
        file = tmp_path / "heroes.json"
        repository = FileHeroRepository(file, catalog)
        repository.save(hero)
        before = file.read_bytes()
        hero.gold = 999
        # Реальные JSON и ФС; только системный сбой замены файла моделируется моком.
        with patch("storage.os.replace", side_effect=OSError("Диск недоступен")):
            with pytest.raises(OSError, match="Диск недоступен"):
                repository.save(hero)
        assert file.read_bytes() == before
        assert list(tmp_path.glob("*.tmp")) == []
        assert FileHeroRepository(file, catalog).find_by_name(hero.name).gold == 50

    def test_proxy_with_real_repository_persists_update_after_restart(self, tmp_path, catalog, hero):
        file = tmp_path / "heroes.json"
        real = FileHeroRepository(file, catalog)
        real.save(hero)
        cache = CachingHeroRepository(real)
        before = real.reads
        first = cache.find_by_name(hero.name)
        assert cache.find_by_name(hero.name) is first
        assert real.reads - before == 1
        first.gold = 123
        cache.save(first)
        restored = CachingHeroRepository(FileHeroRepository(file, create_catalog())).find_by_name(hero.name)
        assert restored is not first
        assert restored.gold == 123
