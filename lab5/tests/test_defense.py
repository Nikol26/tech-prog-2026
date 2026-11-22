"""Поведенческий паттерн Chain of Responsibility: границы, порядок, остановка."""
from unittest.mock import create_autospec, patch
import pytest
from core import Dice
from combat import Damage, DamageHandler, EvasionHandler, ArmorHandler, BarrierHandler


@pytest.mark.unit
class TestBarrierHandler:
    @pytest.mark.parametrize("incoming, absorbed, remainder, capacity", [
        (0, 0, 0, 30), (10, 10, 0, 20), (29, 29, 0, 1),
        (30, 30, 0, 0), (31, 30, 1, 0), (40, 30, 10, 0)
    ])
    def test_damage_equivalence_classes_and_boundaries(self, incoming, absorbed, remainder, capacity):
        # Arrange: запас барьера 30, известный входящий урон.
        barrier, damage = BarrierHandler(30), Damage(incoming)
        # Act: настоящий обработчик изменяет настоящий запрос.
        barrier.handle(damage)
        # Assert: ожидаемые числа получены из правила поглощения, а не из кода обработчика.
        assert (damage.absorbed, damage.amount, barrier.remaining) == (absorbed, remainder, capacity)

    def test_capacity_is_spent_across_hits(self):
        barrier = BarrierHandler(30)
        hits = [Damage(20), Damage(20), Damage(20)]
        for hit in hits:
            barrier.handle(hit)
        assert [(hit.absorbed, hit.amount) for hit in hits] == [(20, 0), (10, 10), (0, 20)]
        assert barrier.remaining == 0

    def test_zero_capacity_forwards_full_damage(self):
        barrier = BarrierHandler(0)
        following = create_autospec(DamageHandler, instance=True)
        barrier.set_next(following)
        damage = Damage(40)
        barrier.handle(damage)
        assert (damage.amount, damage.absorbed) == (40, 0)
        following.handle.assert_called_once_with(damage)

    def test_full_absorption_stops_chain(self):
        barrier = BarrierHandler(30)
        following = create_autospec(DamageHandler, instance=True)
        barrier.set_next(following)
        barrier.handle(Damage(30))
        assert following.mock_calls == []

    def test_rejects_negative_capacity_and_damage(self):
        with pytest.raises(ValueError):
            BarrierHandler(-1)
        with pytest.raises(ValueError):
            Damage(-1)


@pytest.mark.unit
class TestDamageChain:
    @pytest.mark.parametrize("evades", [True, False])
    def test_evasion_checks_dependency_and_stops_or_forwards_same_request(self, evades):
        dice = create_autospec(Dice, instance=True)
        dice.chance.return_value = evades
        following = create_autospec(DamageHandler, instance=True)
        handler = EvasionHandler(0.3)
        handler.set_next(following)
        damage = Damage(40)
        # Подмена в месте использования Dice. Сам EvasionHandler остается настоящим.
        with patch("combat.Dice", return_value=dice) as constructor:
            handler.handle(damage)
        constructor.assert_called_once_with()
        dice.chance.assert_called_once_with(0.3)
        assert (damage.amount, damage.evaded) == (0 if evades else 40, evades)
        if evades:
            assert following.mock_calls == []
        else:
            following.handle.assert_called_once_with(damage)
            assert following.handle.call_args.args[0] is damage

    def test_request_passes_all_real_handlers_in_order(self):
        evasion, armor, barrier = EvasionHandler(0.3), ArmorHandler(0.25), BarrierHandler(30)
        assert evasion.set_next(armor) is armor
        assert armor.set_next(barrier) is barrier
        visited = []

        # Spy сохраняет настоящую реализацию каждого apply и записывает входы.
        def record(label, real_apply):
            def apply(damage):
                visited.append((label, damage.amount))
                real_apply(damage)
            return apply

        damage = Damage(100)
        with patch("combat.Dice") as dice, \
                patch.object(evasion, "apply", side_effect=record("evasion", evasion.apply)) as first, \
                patch.object(armor, "apply", side_effect=record("armor", armor.apply)) as second, \
                patch.object(barrier, "apply", side_effect=record("barrier", barrier.apply)) as third:
            dice.return_value.chance.return_value = False
            evasion.handle(damage)
            for spy in (first, second, third):
                spy.assert_called_once_with(damage)
        assert visited == [("evasion", 100), ("armor", 100), ("barrier", 75)]
        assert (damage.amount, damage.absorbed, damage.evaded, barrier.remaining) == (45, 30, False, 0)

    def test_successful_evasion_preserves_real_barrier(self):
        first, barrier = EvasionHandler(0.3), BarrierHandler(30)
        first.set_next(ArmorHandler(0.25)).set_next(barrier)
        with patch("combat.Dice") as dice:
            dice.return_value.chance.return_value = True
            damage = Damage(100)
            first.handle(damage)
        assert (damage.amount, damage.evaded, barrier.remaining) == (0, True, 30)

    def test_order_changes_result(self):
        armor_first, barrier_first = ArmorHandler(0.25), BarrierHandler(30)
        armor_first.set_next(BarrierHandler(30))
        barrier_first.set_next(ArmorHandler(0.25))
        first, second = Damage(100), Damage(100)
        armor_first.handle(first)
        barrier_first.handle(second)
        assert (first.amount, first.absorbed) == (45, 30)
        assert (second.amount, second.absorbed) == (53, 30)

    def test_zero_damage_skips_entire_chain(self):
        first, barrier = EvasionHandler(0.3), BarrierHandler(30)
        first.set_next(barrier)
        with patch("combat.Dice") as dice:
            damage = Damage(0)
            first.handle(damage)
        dice.assert_not_called()
        assert (damage.amount, barrier.remaining) == (0, 30)

    @pytest.mark.parametrize("defense, incoming, expected", [
        (0, 40, 40), (0.25, 10, 8), (0.3, 30, 21), (1, 40, 1)
    ])
    def test_armor_rounds_and_keeps_minimum_damage(self, defense, incoming, expected):
        damage = Damage(incoming)
        ArmorHandler(defense).handle(damage)
        assert damage.amount == expected

    @pytest.mark.parametrize("handler, value", [
        (ArmorHandler, -0.01), (ArmorHandler, 1.01),
        (EvasionHandler, -0.01), (EvasionHandler, 1.01)
    ])
    def test_invalid_probabilities_raise(self, handler, value):
        with pytest.raises(ValueError):
            handler(value)
