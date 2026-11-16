import pytest

from signcar.config import DrivingConfig
from signcar.driving import (
    STOPPED,
    DriveCommand,
    ManualInput,
    Mode,
    choose_command,
    mix_arcade,
    next_mode,
)

CONFIG = DrivingConfig(max_manual_speed=0.7, vision_timeout_s=1.0)
NO_INPUT = ManualInput()
TOGGLE = ManualInput(toggle_mode=True)
EMERGENCY = ManualInput(emergency_stop=True)


def command(
    mode: Mode,
    manual: ManualInput = NO_INPUT,
    autopilot_speed: float = 0.6,
    controller_connected: bool = True,
    vision_age_s: float = 0.1,
) -> DriveCommand:
    """choose_command with everything healthy unless a test says otherwise."""
    return choose_command(
        mode,
        manual,
        autopilot_speed,
        controller_connected=controller_connected,
        vision_age_s=vision_age_s,
        config=CONFIG,
    )


class TestMixArcade:
    def test_full_throttle_drives_both_sides_forward(self):
        assert mix_arcade(1, 0, max_speed=1) == DriveCommand(1, 1)

    def test_full_reverse_drives_both_sides_backward(self):
        assert mix_arcade(-1, 0, max_speed=1) == DriveCommand(-1, -1)

    def test_steering_right_alone_spins_the_car_in_place(self):
        # As right() in legacy/motor_trial.py: left side forward, right side backward.
        assert mix_arcade(0, 1, max_speed=1) == DriveCommand(1, -1)

    def test_turning_while_driving_slows_the_inner_side(self):
        result = mix_arcade(0.5, 0.25, max_speed=1)
        assert result.left > result.right > 0

    def test_saturated_sides_are_scaled_down_together(self):
        result = mix_arcade(1, 0.5, max_speed=1)
        assert result.left == pytest.approx(1)
        assert result.right == pytest.approx(0.5 / 1.5)

    def test_max_speed_caps_both_sides(self):
        assert mix_arcade(1, 0, max_speed=0.7) == DriveCommand(0.7, 0.7)

    @pytest.mark.parametrize("throttle", [-1, -0.3, 0, 0.6, 1])
    @pytest.mark.parametrize("steering", [-1, -0.5, 0, 0.4, 1])
    def test_never_leaves_the_minus_one_to_one_range(self, throttle, steering):
        result = mix_arcade(throttle, steering, max_speed=1)
        assert -1 <= result.left <= 1
        assert -1 <= result.right <= 1


class TestNextMode:
    def test_toggle_switches_manual_to_auto_and_back(self):
        assert next_mode(Mode.MANUAL, TOGGLE, controller_connected=True) is Mode.AUTO
        assert next_mode(Mode.AUTO, TOGGLE, controller_connected=True) is Mode.MANUAL

    def test_no_buttons_keep_the_mode(self):
        assert next_mode(Mode.AUTO, NO_INPUT, controller_connected=True) is Mode.AUTO

    @pytest.mark.parametrize("mode", [Mode.MANUAL, Mode.AUTO])
    def test_the_emergency_button_stops_any_mode(self, mode):
        assert next_mode(mode, EMERGENCY, controller_connected=True) is Mode.EMERGENCY_STOP

    def test_the_emergency_stop_ignores_the_toggle_button(self):
        result = next_mode(Mode.EMERGENCY_STOP, TOGGLE, controller_connected=True)
        assert result is Mode.EMERGENCY_STOP

    def test_pressing_the_emergency_button_again_releases_it_to_manual(self):
        result = next_mode(Mode.EMERGENCY_STOP, EMERGENCY, controller_connected=True)
        assert result is Mode.MANUAL

    def test_losing_the_controller_in_auto_goes_back_to_manual(self):
        assert next_mode(Mode.AUTO, NO_INPUT, controller_connected=False) is Mode.MANUAL

    def test_losing_the_controller_keeps_an_emergency_stop(self):
        result = next_mode(Mode.EMERGENCY_STOP, NO_INPUT, controller_connected=False)
        assert result is Mode.EMERGENCY_STOP


class TestChooseCommand:
    def test_manual_mode_follows_the_sticks(self):
        assert command(Mode.MANUAL, ManualInput(throttle=1)) == DriveCommand(0.7, 0.7)

    def test_auto_mode_drives_straight_at_the_autopilot_speed(self):
        assert command(Mode.AUTO, autopilot_speed=0.45) == DriveCommand(0.45, 0.45)

    def test_auto_mode_ignores_the_sticks(self):
        result = command(Mode.AUTO, ManualInput(throttle=-1, steering=1), autopilot_speed=0.6)
        assert result == DriveCommand(0.6, 0.6)

    def test_the_emergency_stop_stops_the_car(self):
        assert command(Mode.EMERGENCY_STOP, ManualInput(throttle=1)) == STOPPED

    @pytest.mark.parametrize("mode", [Mode.MANUAL, Mode.AUTO])
    def test_a_lost_controller_stops_the_car(self, mode):
        assert command(mode, ManualInput(throttle=1), controller_connected=False) == STOPPED

    def test_stale_vision_stops_the_car_in_auto_mode(self):
        assert command(Mode.AUTO, vision_age_s=1.5) == STOPPED

    def test_stale_vision_does_not_matter_in_manual_mode(self):
        result = command(Mode.MANUAL, ManualInput(throttle=1), vision_age_s=10)
        assert result == DriveCommand(0.7, 0.7)


class TestDrivingConfig:
    def test_rejects_a_manual_speed_above_full_power(self):
        with pytest.raises(ValueError):
            DrivingConfig(max_manual_speed=1.5)

    def test_rejects_a_vision_timeout_of_zero(self):
        with pytest.raises(ValueError):
            DrivingConfig(vision_timeout_s=0)
