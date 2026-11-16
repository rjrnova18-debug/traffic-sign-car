"""Every number the car uses, in one place.

Defaults come from the original car when it is known (the 0.85 confidence threshold,
the pins and the 100 Hz PWM of legacy/motor_trial.py, the 5 s stop). Values marked
"tune on the car" are first guesses until they are tested on the real hardware.

This module imports nothing from the package, so every other module can import it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterConfig:
    """When to believe a detection, and when a sign counts as confirmed."""

    # From the original car. In the first model's precision-confidence curve
    # (docs/images/precision_confidence_v1.png) precision reaches 1.0 around 0.85-0.92.
    min_confidence: float = 0.85
    # Fraction of the frame's height: a small box means a far-away sign (tune on the car).
    min_box_height: float = 0.12
    # A sign is confirmed when it appears in `min_frames` of the last `window_frames` frames.
    window_frames: int = 5
    min_frames: int = 3

    def __post_init__(self) -> None:
        if not 0 < self.min_confidence <= 1:
            raise ValueError("min_confidence must be in (0, 1]")
        if not 0 <= self.min_box_height <= 1:
            raise ValueError("min_box_height must be in [0, 1]")
        if not 1 <= self.min_frames <= self.window_frames:
            raise ValueError("min_frames must be between 1 and window_frames")


@dataclass(frozen=True)
class AutopilotConfig:
    """How fast the car drives in auto mode, and how long it obeys each sign.

    Speeds are fractions of full power (the PWM duty cycle), from 0 to 1.
    """

    start_speed: float = 0.6  # before any speed limit sign is seen (tune on the car)
    speed_40: float = 0.45  # after a "40" sign (tune on the car)
    speed_80: float = 0.8  # after an "80" sign (tune on the car)
    stop_hold_s: float = 5.0  # from the original car
    stop_cooldown_s: float = 4.0  # time to drive past the stop sign without stopping again
    crossing_speed: float = 0.4  # never faster than this near a crossing
    crossing_hold_s: float = 3.0  # how long the slowdown lasts after the sign is last seen

    def __post_init__(self) -> None:
        speeds = (self.start_speed, self.speed_40, self.speed_80, self.crossing_speed)
        if not all(0 <= speed <= 1 for speed in speeds):
            raise ValueError("speeds must be between 0 and 1")
        if min(self.stop_hold_s, self.stop_cooldown_s, self.crossing_hold_s) < 0:
            raise ValueError("durations cannot be negative")


@dataclass(frozen=True)
class DrivingConfig:
    """Limits for manual driving and for the fail-safe."""

    max_manual_speed: float = 0.7  # full stick = 70 % duty, as in legacy/motor_trial.py
    vision_timeout_s: float = 1.0  # auto mode stops if the latest vision result is older

    def __post_init__(self) -> None:
        if not 0 < self.max_manual_speed <= 1:
            raise ValueError("max_manual_speed must be in (0, 1]")
        if self.vision_timeout_s <= 0:
            raise ValueError("vision_timeout_s must be positive")


@dataclass(frozen=True)
class MotorPins:
    """BCM numbers of the three pins of one TB6612FNG channel (one side of the car)."""

    forward: int  # HIGH (with `backward` LOW) turns the wheels forward
    backward: int  # HIGH (with `forward` LOW) turns them backward
    speed: int  # the PWM input: its duty cycle sets the speed


@dataclass(frozen=True)
class MotorConfig:
    """How the TB6612FNG is wired to the Pi. The pins come from legacy/motor_trial.py."""

    # Channel A (IN1, IN2 and ENA in motor_trial.py) drives the left wheels.
    left: MotorPins = MotorPins(forward=17, backward=18, speed=22)
    # Channel B (IN3, IN4, ENB) drives the right wheels. On the car the right side goes
    # forward when IN4 (GPIO 24) is HIGH, the opposite of the left side, so the two
    # direction pins are swapped here, exactly as forward() does in motor_trial.py.
    right: MotorPins = MotorPins(forward=24, backward=23, speed=25)
    standby_pin: int | None = None  # STBY; None = wired straight to 3.3 V (check on the car)
    pwm_frequency_hz: int = 100  # as in motor_trial.py


@dataclass(frozen=True)
class GamepadConfig:
    """Which stick and buttons do what.

    The numbers change from one gamepad to another: run `signcar --probe-gamepad`
    and move each stick and press each button to find yours.
    """

    throttle_axis: int = 1  # left stick, up and down
    steering_axis: int = 0  # left stick, left and right
    invert_throttle: bool = True  # most gamepads report "stick up" as a negative value
    deadzone: float = 0.15  # a stick closer to the center than this counts as centered
    toggle_mode_button: int = 0
    emergency_stop_button: int = 1
    quit_button: int = 9  # "Start" on many generic gamepads

    def __post_init__(self) -> None:
        if not 0 <= self.deadzone < 1:
            raise ValueError("deadzone must be in [0, 1)")
