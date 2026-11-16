import pytest

from signcar.driving import ManualInput
from signcar.keyboard import ESC, HOLD_S, KeyboardControls


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def keyboard(clock) -> KeyboardControls:
    return KeyboardControls(clock)


def test_no_keys_ask_for_nothing(keyboard):
    keyboard.handle_key(-1)
    assert keyboard.read() == ManualInput()


@pytest.mark.parametrize(
    ("key", "throttle", "steering"),
    [("w", 1, 0), ("s", -1, 0), ("a", 0, -1), ("d", 0, 1), ("W", 1, 0)],
)
def test_movement_keys(keyboard, key, throttle, steering):
    keyboard.handle_key(ord(key))
    result = keyboard.read()
    assert (result.throttle, result.steering) == (throttle, steering)


def test_a_movement_key_lasts_through_the_keyboard_repeat_pause(keyboard, clock):
    keyboard.handle_key(ord("w"))
    clock.now = HOLD_S - 0.01
    assert keyboard.read().throttle == 1
    clock.now = HOLD_S
    assert keyboard.read().throttle == 0


def test_two_movement_keys_combine(keyboard):
    keyboard.handle_key(ord("w"))
    keyboard.handle_key(ord("d"))
    result = keyboard.read()
    assert (result.throttle, result.steering) == (1, 1)


@pytest.mark.parametrize(
    ("key", "field"), [("m", "toggle_mode"), (" ", "emergency_stop"), ("q", "quit")]
)
def test_button_keys_count_once(keyboard, key, field):
    keyboard.handle_key(ord(key))
    assert getattr(keyboard.read(), field) is True
    assert getattr(keyboard.read(), field) is False  # already used


def test_escape_quits(keyboard):
    keyboard.handle_key(ESC)
    assert keyboard.read().quit is True


def test_the_keyboard_is_always_connected(keyboard):
    assert keyboard.connected is True
