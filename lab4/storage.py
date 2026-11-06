"""Файловое хранилище героев и кэширующий Proxy с тем же контрактом."""
import json
import os
from pathlib import Path
import tempfile
from typing import Protocol
from heroes import HeroBuilder, KITS
from items import ENCHANTMENTS


class HeroRepository(Protocol):
    def find_all(self): ...
    def find_by_name(self, name): ...
    def save(self, hero): ...


class FileHeroRepository:
    def __init__(self, file, catalog):
        self.file, self.catalog = Path(file), catalog
        self.reads = 0

    def _read_records(self):
        self.reads += 1
        if not self.file.exists():
            return []
        try:
            text = self.file.read_text(encoding="utf-8-sig")
            records = json.loads(text) if text.strip() else []
            if not isinstance(records, list):
                raise ValueError("Ожидался массив героев")
            names = [record["name"] for record in records]
            if len(names) != len(set(names)):
                raise ValueError("Имена героев повторяются")
            return records
        except (ValueError, KeyError, TypeError, UnicodeError) as error:
            raise ValueError(f"Некорректное сохранение {self.file.name}: {error}") from error

    def find_all(self):
        return [self._restore(record) for record in self._read_records()]

    def find_by_name(self, name):
        return next((hero for hero in self.find_all() if hero.name == name), None)

    def _item_snapshot(self, item):
        return {"code": item.code,
                "enchantments": [next(code for code, value in ENCHANTMENTS.items() if value == e)
                                 for e in item.enchantments]}

    def _snapshot(self, hero):
        return dict(name=hero.name, hero_class=hero.hero_class.code, level=hero.level,
                    experience=hero.experience, gold=hero.gold,
                    weapon=self._item_snapshot(hero.weapon), armor=self._item_snapshot(hero.armor),
                    inventory=[self._item_snapshot(item) for item in hero.inventory],
                    achievements=sorted(hero.achievements))

    def _restore_item(self, record):
        item = self.catalog.create(record["code"])
        for code in record["enchantments"]:
            item.enchant(ENCHANTMENTS[code])
        return item

    def _restore(self, record):
        try:
            kind = next(kind for kind in KITS if kind.code == record["hero_class"])
            name = record["name"]
            if not isinstance(name, str) or name != name.strip():
                raise ValueError("Некорректное имя")
            inventory, achievements = record["inventory"], record["achievements"]
            if not isinstance(inventory, list) or not isinstance(achievements, list):
                raise ValueError("Инвентарь и достижения должны быть массивами")
            return (HeroBuilder(self.catalog).set_name(name).set_class(kind)
                    .set_level(record["level"]).set_gold(record["gold"])
                    .set_experience(record["experience"])
                    .set_equipment(self._restore_item(record["weapon"]),
                                   self._restore_item(record["armor"]))
                    .set_inventory([self._restore_item(item) for item in inventory])
                    .set_achievements(achievements).build())
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            raise ValueError(f"Данные героя в {self.file.name} повреждены: {error}") from error

    def save(self, hero):
        # Сначала читаем и проверяем старые данные: повреждённый файл не затирается.
        others = [self._snapshot(other) for other in self.find_all() if other.name != hero.name]
        snapshot = self._snapshot(hero)
        self._restore(snapshot)  # Не записываем недопустимое состояние.
        others.append(snapshot)
        self.file.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=self.file.name + ".", suffix=".tmp",
                                         dir=self.file.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(others, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


class CachingHeroRepository:
    """Proxy: чтения из памяти, запись проходит в настоящее хранилище."""
    def __init__(self, target: HeroRepository):
        self.target, self._cache = target, None

    def _cached(self):
        if self._cache is None:
            self._cache = {hero.name: hero for hero in self.target.find_all()}
        return self._cache

    def find_all(self):
        return list(self._cached().values())

    def find_by_name(self, name):
        return self._cached().get(name)

    def save(self, hero):
        cache = self._cached()
        self.target.save(hero)
        cache[hero.name] = hero
