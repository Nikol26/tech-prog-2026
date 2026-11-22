"""Порождающие паттерны: Singleton и Prototype."""
import pytest
from core import Dice
from items import FIERY, SHARP


@pytest.mark.unit
class TestDiceSingleton:
    def test_returns_same_instance(self):
        assert Dice() is Dice()

    @pytest.mark.parametrize("low, high", [(1, 6), (-10, -1), (-3, 3), (0, 0), (7, 7)])
    def test_roll_inclusive_bounds(self, low, high):
        for _ in range(100):
            result = Dice().roll(low, high)
            assert low <= result <= high

    def test_equal_bounds_return_only_value(self):
        assert Dice().roll(7, 7) == 7

    @pytest.mark.parametrize("probability, expected", [(0, False), (1, True)])
    def test_certain_and_impossible_chance(self, probability, expected):
        assert all(Dice().chance(probability) is expected for _ in range(100))

    def test_pick_preserves_single_object_identity(self):
        element = object()
        assert Dice().pick([element]) is element

    def test_pick_returns_given_option(self):
        options = ["меч", "щит", "посох"]
        assert all(Dice().pick(options) in options for _ in range(100))

    def test_seed_repeats_roll_chance_and_pick_sequence(self):
        def sequence():
            return [(Dice().roll(1, 100), Dice().chance(0.3), Dice().pick("abc"))
                    for _ in range(20)]
        Dice().reseed(42)
        first = sequence()
        Dice().reseed(42)
        assert sequence() == first

    def test_second_constructor_does_not_reset_generator(self):
        Dice().reseed(42)
        expected = [Dice().roll(1, 100) for _ in range(3)]
        Dice().reseed(42)
        first = Dice().roll(1, 100)
        another = Dice()
        assert [first, another.roll(1, 100), another.roll(1, 100)] == expected

    def test_invalid_bounds_raise(self):
        with pytest.raises(ValueError):
            Dice().roll(5, 1)

    def test_empty_pick_raises(self):
        with pytest.raises(IndexError):
            Dice().pick([])


@pytest.mark.unit
class TestItemPrototype:
    def test_copy_preserves_type_and_values(self, catalog):
        original = catalog.create("iron")
        original.enchant(SHARP)
        clone = original.copy()
        assert clone is not original
        assert type(clone) is type(original)
        assert (clone.code, clone.name, clone.price, clone.damage) == (
            "iron", "Железный меч", 100, 20
        )
        assert clone.enchantments == [SHARP]
        assert clone.enchantments is not original.enchantments

    def test_mutations_do_not_affect_prototype_or_other_copies(self, catalog):
        first, second = catalog.create("iron"), catalog.create("iron")
        first.enchant(FIERY)
        assert first.damage == 23
        assert first.price == 130
        assert second.enchantments == []
        assert catalog.create("iron").enchantments == []

    def test_register_takes_snapshot(self, catalog):
        prototype = catalog.create("iron")
        catalog.register(prototype)
        prototype.enchant(FIERY)
        assert catalog.create("iron").enchantments == []
