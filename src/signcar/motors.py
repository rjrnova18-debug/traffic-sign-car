"""Turns drive commands into wheel movement.

- Tb6612Motors drives the real TB6612FNG H-bridge through the Pi's GPIO pins.
- SimulatedMotors only remembers the last command, for running on a PC.

Both have the same three methods (drive, stop, close), so the rest of the program
never knows which one it is using.

gpiozero replaces the RPi.GPIO of the original car: RPi.GPIO does not work on the
Raspberry Pi 5, whose pins are run by a new chip (the RP1). gpiozero is imported
only when the real motors are created, so a PC without it can still simulate.
"""

import time
from collections.abc import Callable
from typing import Any, Protocol

from signcar.config import MotorConfig, MotorPins
from signcar.driving import STOPPED, DriveCommand


class Motors(Protocol):
    def drive(self, command: DriveCommand) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class _Side:
    """One channel of the TB6612FNG: two direction pins and one speed (PWM) pin.

    | speed | forward pin | backward pin | PWM duty  |
    |-------|-------------|--------------|-----------|
    |  > 0  | HIGH        | LOW          | speed     |
    |  < 0  | LOW         | HIGH         | -speed    |
    |  = 0  | LOW         | LOW          | 0 (coast) |
    """

    def __init__(self, pins: MotorPins, frequency_hz: int, pin_factory: Any) -> None:
        from gpiozero import DigitalOutputDevice, PWMOutputDevice

        self._forward = DigitalOutputDevice(pins.forward, pin_factory=pin_factory)
        self._backward = DigitalOutputDevice(pins.backward, pin_factory=pin_factory)
        self._speed = PWMOutputDevice(pins.speed, frequency=frequency_hz, pin_factory=pin_factory)

    def set(self, speed: float) -> None:
        """Speed from -1 to 1: the sign picks the direction, the size the duty cycle."""
        speed = max(-1.0, min(1.0, speed))
        self._forward.value = speed > 0
        self._backward.value = speed < 0
        self._speed.value = abs(speed)

    def close(self) -> None:
        for device in (self._forward, self._backward, self._speed):
            device.close()


class Tb6612Motors:
    """The real motors. `pin_factory` lets the tests use gpiozero's simulated pins."""

    def __init__(self, config: MotorConfig, pin_factory: Any = None) -> None:
        self._left = _Side(config.left, config.pwm_frequency_hz, pin_factory)
        self._right = _Side(config.right, config.pwm_frequency_hz, pin_factory)
        self._standby = None
        if config.standby_pin is not None:
            from gpiozero import DigitalOutputDevice

            # STBY must be HIGH for the driver to work.
            self._standby = DigitalOutputDevice(
                config.standby_pin, initial_value=True, pin_factory=pin_factory
            )

    def drive(self, command: DriveCommand) -> None:
        self._left.set(command.left)
        self._right.set(command.right)

    def stop(self) -> None:
        self.drive(STOPPED)

    def close(self) -> None:
        """Stop the wheels and give the pins back. Always called on the way out."""
        self.stop()
        self._left.close()
        self._right.close()
        if self._standby is not None:
            self._standby.close()


class SimulatedMotors:
    """Stands in for the motors on a PC. It remembers the last command."""

    def __init__(self) -> None:
        self.command = STOPPED

    def drive(self, command: DriveCommand) -> None:
        self.command = command

    def stop(self) -> None:
        self.command = STOPPED

    def close(self) -> None:
        self.stop()


# Each side alone, both directions, then both together. Slow, and with pauses.
MOTOR_TEST_STEPS = [
    ("left side forward", DriveCommand(0.4, 0.0)),
    ("left side backward", DriveCommand(-0.4, 0.0)),
    ("right side forward", DriveCommand(0.0, 0.4)),
    ("right side backward", DriveCommand(0.0, -0.4)),
    ("both sides forward", DriveCommand(0.4, 0.4)),
    ("spin right (left forward, right backward)", DriveCommand(0.4, -0.4)),
]


def run_motor_test(
    motors: Motors,
    step_s: float = 1.5,
    sleep: Callable[[float], None] = time.sleep,
    say: Callable[[str], None] = print,
) -> None:
    """Spin each side both ways, one step at a time. Run it with the wheels in the air.

    If a side turns the wrong way, swap its `forward` and `backward` pins in MotorConfig.
    """
    for description, command in MOTOR_TEST_STEPS:
        say(description)
        motors.drive(command)
        sleep(step_s)
        motors.stop()
        sleep(0.5)
