"""The conversion from gamepad readings to ManualInput (no pygame or gamepad needed)."""

import pytest

from signcar.config import GamepadConfig
from signcar.driving import ManualInput
from signcar.gamepad import apply_deadzone, to_manual_input

CONFIG = GamepadConfig(
    throttle_axis=1,
    steering_axis=0,
    invert_throttle=True,
    deadzone=0.2,
    toggle_mode_button=0,
    emergency_stop_button=1,
    quit_button=9,
)


class TestApplyDeadzone:
    @pytest.mark.parametrize("value", [0.0, 0.1, -0.19])
    def test_small_movements_count_as_centered(self, value):
        assert apply_deadzone(value, 0.2) == 0

    @pytest.mark.parametrize(("value", "expected"), [(1.0, 1.0), (-1.0, -1.0), (0.6, 0.5)])
    def test_the_rest_is_stretched_to_the_full_range(self, value, expected):
        assert apply_deadzone(value, 0.2) == pytest.approx(expected)

    def test_values_past_the_end_are_capped(self):
        assert apply_deadzone(1.05, 0.2) == 1.0


class TestToManualInput:
    def test_centered_sticks_and_no_buttons_ask_for_nothing(self):
        assert to_manual_input([0.0, 0.0], set(), CONFIG) == ManualInput()

    def test_stick_up_means_forward(self):
        # Gamepads report "up" as -1, so the throttle is inverted.
        assert to_manual_input([0.0, -1.0], set(), CONFIG).throttle == pytest.approx(1.0)

    def test_stick_right_means_turn_right(self):
        assert to_manual_input([1.0, 0.0], set(), CONFIG).steering == pytest.approx(1.0)

    def test_buttons_map_to_their_actions(self):
        result = to_manual_input([0.0, 0.0], {0, 1, 9}, CONFIG)
        assert (result.toggle_mode, result.emergency_stop, result.quit) == (True, True, True)

    def test_other_buttons_are_ignored(self):
        assert to_manual_input([0.0, 0.0], {4, 5}, CONFIG) == ManualInput()

    def test_a_gamepad_with_fewer_axes_reads_them_as_centered(self):
        assert to_manual_input([], set(), CONFIG) == ManualInput()


def test_config_rejects_a_deadzone_of_one():
    with pytest.raises(ValueError):
        GamepadConfig(deadzone=1.0)
