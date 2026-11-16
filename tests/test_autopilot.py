import pytest

from signcar.autopilot import Autopilot, AutopilotState
from signcar.config import AutopilotConfig
from signcar.signs import Sign

CONFIG = AutopilotConfig(
    start_speed=0.6,
    speed_40=0.45,
    speed_80=0.8,
    stop_hold_s=5.0,
    stop_cooldown_s=4.0,
    crossing_speed=0.4,
    crossing_hold_s=3.0,
)

STOP = {Sign.STOP}
RED = {Sign.RED_LIGHT}
GREEN = {Sign.GREEN_LIGHT}
NOTHING: set[Sign] = set()


@pytest.fixture
def autopilot() -> Autopilot:
    return Autopilot(CONFIG)


def test_starts_cruising_at_the_start_speed(autopilot):
    assert autopilot.update(NOTHING, now=0) == 0.6
    assert autopilot.state is AutopilotState.CRUISING


class TestStopSign:
    def test_stops_for_the_whole_hold(self, autopilot):
        autopilot.update(STOP, now=0)
        assert autopilot.update(NOTHING, now=4.9) == 0
        assert autopilot.state is AutopilotState.STOPPED_AT_SIGN

    def test_drives_on_after_the_hold(self, autopilot):
        autopilot.update(STOP, now=0)
        assert autopilot.update(NOTHING, now=5.0) == 0.6

    def test_ignores_the_same_stop_sign_while_driving_past_it(self, autopilot):
        autopilot.update(STOP, now=0)
        assert autopilot.update(STOP, now=5.0) == 0.6
        assert autopilot.update(STOP, now=8.9) == 0.6

    def test_obeys_a_new_stop_sign_after_the_cooldown(self, autopilot):
        autopilot.update(STOP, now=0)
        autopilot.update(NOTHING, now=5.0)
        assert autopilot.update(STOP, now=9.0) == 0


class TestTrafficLight:
    def test_a_red_light_stops_the_car(self, autopilot):
        assert autopilot.update(RED, now=0) == 0
        assert autopilot.state is AutopilotState.WAITING_FOR_GREEN

    def test_keeps_waiting_when_the_red_light_leaves_the_view(self, autopilot):
        autopilot.update(RED, now=0)
        assert autopilot.update(NOTHING, now=60) == 0

    def test_a_green_light_lets_the_car_go(self, autopilot):
        autopilot.update(RED, now=0)
        assert autopilot.update(GREEN, now=1) == 0.6

    def test_green_and_red_together_keep_the_car_waiting(self, autopilot):
        autopilot.update(RED, now=0)
        assert autopilot.update(GREEN | RED, now=1) == 0

    def test_a_green_light_while_cruising_changes_nothing(self, autopilot):
        assert autopilot.update(GREEN, now=0) == 0.6


class TestSpeedLimits:
    @pytest.mark.parametrize(("sign", "speed"), [(Sign.SPEED_40, 0.45), (Sign.SPEED_80, 0.8)])
    def test_a_speed_limit_sets_the_cruise_speed(self, autopilot, sign, speed):
        assert autopilot.update({sign}, now=0) == speed

    def test_the_cruise_speed_is_kept_after_the_sign_is_gone(self, autopilot):
        autopilot.update({Sign.SPEED_40}, now=0)
        assert autopilot.update(NOTHING, now=30) == 0.45

    def test_two_limits_at_once_obey_the_lower_one(self, autopilot):
        assert autopilot.update({Sign.SPEED_40, Sign.SPEED_80}, now=0) == 0.45

    def test_a_limit_seen_while_stopped_is_used_when_driving_on(self, autopilot):
        autopilot.update(STOP, now=0)
        autopilot.update({Sign.SPEED_80}, now=2)
        assert autopilot.update(NOTHING, now=5) == 0.8


class TestCrossing:
    def test_slows_down_near_a_crossing(self, autopilot):
        assert autopilot.update({Sign.CROSSING}, now=0) == 0.4
        assert autopilot.state is AutopilotState.SLOWING_FOR_CROSSING

    def test_goes_back_to_cruise_speed_after_the_hold(self, autopilot):
        autopilot.update({Sign.CROSSING}, now=0)
        assert autopilot.update(NOTHING, now=3.0) == 0.6

    def test_seeing_the_sign_again_keeps_the_car_slow(self, autopilot):
        autopilot.update({Sign.CROSSING}, now=0)
        autopilot.update({Sign.CROSSING}, now=2)
        assert autopilot.update(NOTHING, now=4.9) == 0.4

    def test_never_speeds_up_when_the_cruise_speed_is_already_lower(self):
        slow_autopilot = Autopilot(AutopilotConfig(start_speed=0.3, crossing_speed=0.4))
        assert slow_autopilot.update({Sign.CROSSING}, now=0) == 0.3


class TestPriority:
    def test_stop_wins_over_a_red_light_and_then_the_car_waits(self, autopilot):
        autopilot.update(STOP | RED, now=0)
        assert autopilot.state is AutopilotState.STOPPED_AT_SIGN
        autopilot.update(RED, now=5)
        assert autopilot.state is AutopilotState.WAITING_FOR_GREEN

    def test_a_red_light_wins_over_a_crossing(self, autopilot):
        autopilot.update(RED | {Sign.CROSSING}, now=0)
        assert autopilot.state is AutopilotState.WAITING_FOR_GREEN

    def test_a_stop_sign_interrupts_a_crossing_slowdown(self, autopilot):
        autopilot.update({Sign.CROSSING}, now=0)
        assert autopilot.update(STOP, now=1) == 0


def test_reset_forgets_states_limits_and_cooldowns(autopilot):
    autopilot.update(STOP | {Sign.SPEED_40}, now=0)
    autopilot.reset()
    assert autopilot.state is AutopilotState.CRUISING
    assert autopilot.update(NOTHING, now=1) == 0.6
    assert autopilot.update(STOP, now=1) == 0  # no cooldown left over


class TestAutopilotConfig:
    def test_rejects_a_speed_above_full_power(self):
        with pytest.raises(ValueError):
            AutopilotConfig(speed_80=1.2)

    def test_rejects_a_negative_duration(self):
        with pytest.raises(ValueError):
            AutopilotConfig(stop_hold_s=-1)
