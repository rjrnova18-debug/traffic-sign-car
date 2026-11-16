"""Reads the wireless gamepad (2.4 GHz USB receiver) and turns it into ManualInput.

pygame-ce reads the gamepad on the Pi (with no screen) and on Windows, so the same
controller can be tested on the PC. pygame is imported only when a Gamepad is created;
the conversion from sticks and buttons to ManualInput is plain Python and is tested
on its own.
"""

import os

from signcar.config import GamepadConfig
from signcar.driving import ManualInput


def apply_deadzone(value: float, deadzone: float) -> float:
    """Ignore small stick movements, then stretch the rest back to the full -1 to 1 range.

    Without a deadzone, a stick that rests slightly off-center would creep the car forward.
    """
    if abs(value) < deadzone:
        return 0.0
    stretched = (abs(value) - deadzone) / (1 - deadzone)
    return min(1.0, stretched) if value > 0 else -min(1.0, stretched)


def to_manual_input(axes: list[float], pressed: set[int], config: GamepadConfig) -> ManualInput:
    """Convert one reading of the gamepad (stick positions + buttons just pressed)."""

    def axis(index: int) -> float:
        raw = axes[index] if index < len(axes) else 0.0
        return apply_deadzone(raw, config.deadzone)

    throttle = axis(config.throttle_axis)
    return ManualInput(
        throttle=-throttle if config.invert_throttle else throttle,
        steering=axis(config.steering_axis),
        toggle_mode=config.toggle_mode_button in pressed,
        emergency_stop=config.emergency_stop_button in pressed,
        quit=config.quit_button in pressed,
    )


class Gamepad:
    """The real gamepad. Survives being switched off or unplugged.

    While no gamepad is connected, `connected` is False and `read()` returns a
    centered input with no buttons; the fail-safe in driving.py then stops the car.
    """

    def __init__(self, config: GamepadConfig) -> None:
        self._pygame = _start_pygame()
        self._config = config
        self._joystick = None  # SDL announces gamepads already plugged in as "added" events

    @property
    def connected(self) -> bool:
        return self._joystick is not None

    def read(self) -> ManualInput:
        """Process the pending gamepad events and return this tick's input."""
        pressed = self._handle_events()
        if self._joystick is None:
            return ManualInput()
        axes = [self._joystick.get_axis(i) for i in range(self._joystick.get_numaxes())]
        return to_manual_input(axes, pressed, self._config)

    def close(self) -> None:
        self._pygame.quit()

    def _handle_events(self) -> set[int]:
        """Track the gamepad coming and going, and collect the buttons just pressed."""
        pygame = self._pygame
        pressed = set()
        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEADDED and self._joystick is None:
                self._joystick = pygame.joystick.Joystick(event.device_index)
            elif event.type == pygame.JOYDEVICEREMOVED and self._is_ours(event.instance_id):
                self._joystick = None
            elif event.type == pygame.JOYBUTTONDOWN:
                pressed.add(event.button)
        return pressed

    def _is_ours(self, instance_id: int) -> bool:
        return self._joystick is not None and self._joystick.get_instance_id() == instance_id


def probe() -> None:
    """Print every stick movement and button press, to fill in GamepadConfig. Ctrl+C quits."""
    pygame = _start_pygame()
    joysticks = []  # keep a reference, or pygame closes the gamepad
    print("Move each stick and press each button. Ctrl+C to quit.")
    try:
        while True:
            event = pygame.event.wait()
            if event.type == pygame.JOYDEVICEADDED:
                joysticks.append(pygame.joystick.Joystick(event.device_index))
                print(f"Connected: {joysticks[-1].get_name()}")
            elif event.type == pygame.JOYBUTTONDOWN:
                print(f"button {event.button}")
            elif event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.5:
                print(f"axis {event.axis} = {event.value:+.2f}")
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


def _start_pygame():
    """Import pygame and start only what the gamepad needs. Works without a screen."""
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # no banner in the console
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # the event queue needs a video driver
    # Deliver gamepad events even when no pygame window has the focus.
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    import pygame

    pygame.display.init()
    pygame.joystick.init()
    return pygame
