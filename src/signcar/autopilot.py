"""Decides the car's speed in auto mode from the confirmed signs.

In auto mode the car always drives straight: the autopilot only chooses how fast.
It is a state machine:

    CRUISING ──stop──────────▶ STOPPED_AT_SIGN ──5 s──▶ CRUISING (stop signs ignored a while)
    CRUISING ──red light─────▶ WAITING_FOR_GREEN ──green (and no red)──▶ CRUISING
    CRUISING ──crossing──────▶ SLOWING_FOR_CROSSING ──3 s──▶ CRUISING
    any state ──speed limit──▶ same state, new cruise speed

Pure Python. Time comes in as `now` (seconds), so tests can jump forward instantly.
"""

from enum import Enum

from signcar.config import AutopilotConfig
from signcar.signs import Sign


class AutopilotState(Enum):
    CRUISING = "cruising"
    STOPPED_AT_SIGN = "stopped at sign"
    WAITING_FOR_GREEN = "waiting for green"
    SLOWING_FOR_CROSSING = "slowing for crossing"


class Autopilot:
    def __init__(self, config: AutopilotConfig) -> None:
        self._config = config
        self.reset()

    def reset(self) -> None:
        """Start fresh, as when the operator switches to auto mode."""
        self.state = AutopilotState.CRUISING
        self.cruise_speed = self._config.start_speed
        self._state_ends_at = 0.0  # when the stop hold or the crossing slowdown ends
        self._ignore_stops_until = 0.0  # the stop cooldown

    def update(self, signs: set[Sign], now: float) -> float:
        """Take the signs confirmed in the latest frame and return the speed (0-1)."""
        self._remember_speed_limit(signs)
        self._end_timed_state(now)
        self._react_to(signs, now)
        return self.speed

    @property
    def speed(self) -> float:
        """The speed for the current state, from 0 (stopped) to 1 (full power)."""
        if self.state in (AutopilotState.STOPPED_AT_SIGN, AutopilotState.WAITING_FOR_GREEN):
            return 0.0
        if self.state is AutopilotState.SLOWING_FOR_CROSSING:
            return min(self._config.crossing_speed, self.cruise_speed)
        return self.cruise_speed

    def _remember_speed_limit(self, signs: set[Sign]) -> None:
        """A speed limit changes the cruise speed in every state, even while stopped."""
        limits = []
        if Sign.SPEED_40 in signs:
            limits.append(self._config.speed_40)
        if Sign.SPEED_80 in signs:
            limits.append(self._config.speed_80)
        if limits:
            self.cruise_speed = min(limits)  # two limits at once: obey the safer one

    def _end_timed_state(self, now: float) -> None:
        if now < self._state_ends_at:
            return
        if self.state is AutopilotState.STOPPED_AT_SIGN:
            self.state = AutopilotState.CRUISING
            self._ignore_stops_until = now + self._config.stop_cooldown_s
        elif self.state is AutopilotState.SLOWING_FOR_CROSSING:
            self.state = AutopilotState.CRUISING

    def _react_to(self, signs: set[Sign], now: float) -> None:
        if self.state is AutopilotState.STOPPED_AT_SIGN:
            return  # the hold always lasts its full time

        if self.state is AutopilotState.WAITING_FOR_GREEN:
            # A green light only counts if no red light is confirmed at the same time.
            if Sign.GREEN_LIGHT in signs and Sign.RED_LIGHT not in signs:
                self.state = AutopilotState.CRUISING
            return

        # Cruising or slowing down: the most important sign wins.
        if Sign.STOP in signs and now >= self._ignore_stops_until:
            self.state = AutopilotState.STOPPED_AT_SIGN
            self._state_ends_at = now + self._config.stop_hold_s
        elif Sign.RED_LIGHT in signs:
            self.state = AutopilotState.WAITING_FOR_GREEN
        elif Sign.CROSSING in signs:
            # Seeing the sign again keeps the car slow for longer.
            self.state = AutopilotState.SLOWING_FOR_CROSSING
            self._state_ends_at = now + self._config.crossing_hold_s
