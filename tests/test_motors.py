"""The motor driver, tested on gpiozero's simulated pins (no Raspberry Pi needed)."""

import pytest
from gpiozero import DigitalOutputDevice
from gpiozero.pins.mock import MockFactory, MockPWMPin

from signcar.config import MotorConfig
from signcar.driving import STOPPED, DriveCommand
from signcar.motors import MOTOR_TEST_STEPS, SimulatedMotors, Tb6612Motors, run_motor_test

# The pins of legacy/motor_trial.py.
LEFT_FORWARD, LEFT_BACKWARD, LEFT_SPEED = 17, 18, 22
RIGHT_FORWARD, RIGHT_BACKWARD, RIGHT_SPEED = 24, 23, 25


@pytest.fixture
def factory() -> MockFactory:
    return MockFactory(pin_class=MockPWMPin)


@pytest.fixture
def motors(factory):
    motors = Tb6612Motors(MotorConfig(), pin_factory=factory)
    yield motors
    motors.close()


def level(factory: MockFactory, pin: int) -> float:
    """What a simulated pin outputs: 0 or 1 for direction pins, the duty cycle for PWM."""
    return factory.pin(pin).state


def test_forward_drives_both_sides_like_motor_trial_forward(factory, motors):
    motors.drive(DriveCommand.straight(0.7))
    assert (level(factory, LEFT_FORWARD), level(factory, LEFT_BACKWARD)) == (1, 0)
    assert (level(factory, RIGHT_FORWARD), level(factory, RIGHT_BACKWARD)) == (1, 0)
    assert level(factory, LEFT_SPEED) == pytest.approx(0.7)
    assert level(factory, RIGHT_SPEED) == pytest.approx(0.7)


def test_reverse_flips_the_direction_pins(factory, motors):
    motors.drive(DriveCommand.straight(-0.5))
    assert (level(factory, LEFT_FORWARD), level(factory, LEFT_BACKWARD)) == (0, 1)
    assert level(factory, LEFT_SPEED) == pytest.approx(0.5)


def test_spinning_right_matches_motor_trial_right(factory, motors):
    # right() in motor_trial.py: IN1 HIGH, IN2 LOW (left forward), IN4 LOW, IN3 HIGH.
    motors.drive(DriveCommand(1, -1))
    assert (level(factory, LEFT_FORWARD), level(factory, LEFT_BACKWARD)) == (1, 0)
    assert (level(factory, RIGHT_FORWARD), level(factory, RIGHT_BACKWARD)) == (0, 1)


def test_stop_turns_every_pin_off(factory, motors):
    motors.drive(DriveCommand(0.8, -0.3))
    motors.stop()
    for pin in (LEFT_FORWARD, LEFT_BACKWARD, LEFT_SPEED, RIGHT_FORWARD, RIGHT_BACKWARD):
        assert level(factory, pin) == 0


def test_speeds_beyond_full_power_are_clamped(factory, motors):
    motors.drive(DriveCommand.straight(1.5))
    assert level(factory, LEFT_SPEED) == pytest.approx(1.0)


def test_close_gives_the_pins_back(factory):
    motors = Tb6612Motors(MotorConfig(), pin_factory=factory)
    motors.close()
    DigitalOutputDevice(LEFT_FORWARD, pin_factory=factory).close()  # would fail if still in use


def test_the_standby_pin_is_set_high_when_wired(factory):
    motors = Tb6612Motors(MotorConfig(standby_pin=27), pin_factory=factory)
    assert level(factory, 27) == 1
    motors.close()


def test_simulated_motors_remember_the_last_command():
    motors = SimulatedMotors()
    motors.drive(DriveCommand(0.5, 0.2))
    assert motors.command == DriveCommand(0.5, 0.2)
    motors.close()
    assert motors.command == STOPPED


def test_the_motor_test_runs_every_step_and_ends_stopped():
    class RecordingMotors(SimulatedMotors):
        def __init__(self):
            super().__init__()
            self.history = []

        def drive(self, command):
            super().drive(command)
            self.history.append(command)

    motors, said = RecordingMotors(), []
    run_motor_test(motors, sleep=lambda seconds: None, say=said.append)

    assert said[0] == "left side forward"
    assert motors.history == [command for _, command in MOTOR_TEST_STEPS]
    assert motors.command == STOPPED
