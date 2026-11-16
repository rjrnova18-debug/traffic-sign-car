"""Who drives and how: the modes, the operator's input and the fail-safe.

Pure Python. On every control tick, app.py asks this module two questions:
which mode the car is in now (`next_mode`) and what the wheels must do (`choose_command`).
The fail-safe rule behind both answers: when in doubt, stop.
"""

from dataclasses import dataclass
from enum import Enum

from signcar.config import DrivingConfig


class Mode(Enum):
    MANUAL = "manual"  # the operator drives with the gamepad
    AUTO = "auto"  # the car drives straight and the autopilot sets the speed
    EMERGENCY_STOP = "emergency stop"  # nobody drives until the operator releases it


@dataclass(frozen=True)
class ManualInput:
    """What the operator asks for on one control tick."""

    throttle: float = 0.0  # -1 (full reverse) to 1 (full forward)
    steering: float = 0.0  # -1 (left) to 1 (right)
    # Buttons are True only on the tick they were pressed, not while held down.
    toggle_mode: bool = False  # switch between manual and auto
    emergency_stop: bool = False  # start the emergency stop, or release it
    quit: bool = False  # close the program


@dataclass(frozen=True)
class DriveCommand:
    """The speed for each side of the car, from -1 (full reverse) to 1 (full forward)."""

    left: float
    right: float

    @classmethod
    def straight(cls, speed: float) -> "DriveCommand":
        return cls(speed, speed)


STOPPED = DriveCommand(0.0, 0.0)


def mix_arcade(throttle: float, steering: float, max_speed: float) -> DriveCommand:
    """Turn "how fast" and "how much to turn" into a speed for each side.

    The car steers like a tank: to turn right, the left wheels go faster than the
    right ones (full steering with no throttle spins it in place). If one side would
    go past full speed, both are scaled down together so the turn keeps its shape.
    """
    left = throttle + steering
    right = throttle - steering
    biggest = max(1.0, abs(left), abs(right))
    return DriveCommand(left / biggest * max_speed, right / biggest * max_speed)


def next_mode(mode: Mode, manual: ManualInput, *, controller_connected: bool) -> Mode:
    """The mode for this tick, from the previous mode and the buttons pressed."""
    if manual.emergency_stop:
        # The same button starts and releases it. Releasing goes to manual, never to auto.
        return Mode.MANUAL if mode is Mode.EMERGENCY_STOP else Mode.EMERGENCY_STOP
    if mode is Mode.EMERGENCY_STOP:
        return mode  # only the emergency button releases it
    if not controller_connected:
        # Nobody could take over, so nobody drives. Back in manual with the sticks
        # centered, nothing moves when the controller comes back.
        return Mode.MANUAL
    if manual.toggle_mode:
        return Mode.AUTO if mode is Mode.MANUAL else Mode.MANUAL
    return mode


def choose_command(
    mode: Mode,
    manual: ManualInput,
    autopilot_speed: float,
    *,
    controller_connected: bool,
    vision_age_s: float,
    config: DrivingConfig,
) -> DriveCommand:
    """What the wheels must do on this tick. Every doubt ends in STOPPED.

    `vision_age_s` is how long ago the latest camera frame was analyzed.
    """
    if mode is Mode.EMERGENCY_STOP or not controller_connected:
        return STOPPED
    if mode is Mode.MANUAL:
        return mix_arcade(manual.throttle, manual.steering, config.max_manual_speed)
    # Auto mode trusts the autopilot only while the vision is up to date.
    if vision_age_s > config.vision_timeout_s:
        return STOPPED
    return DriveCommand.straight(autopilot_speed)
