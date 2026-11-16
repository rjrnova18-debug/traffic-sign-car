"""Drive the simulation from the keyboard, in the HUD window.

    W / S   forward / backward          M       manual <-> auto
    A / D   turn left / right           Space   emergency stop (press again to release)
                                        Q, Esc  quit

The HUD window hands over each key it receives (handle_key), and the control loop
reads the result like a gamepad (read). Plain Python: no OpenCV needed here.
"""

import time
from collections.abc import Callable

from signcar.driving import ManualInput

# A held key reaches the program as one press, a pause of about half a second, and
# then fast repeats. Keeping each press alive this long bridges that pause.
HOLD_S = 0.6

MOVE_KEYS = {"w", "s", "a", "d"}
ESC = 27


class KeyboardControls:
    connected = True  # unlike the gamepad, a keyboard cannot run out of battery

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._held_until: dict[str, float] = {}  # movement key -> when its effect ends
        self._pressed: set[str] = set()  # button keys since the last read

    def handle_key(self, key: int) -> None:
        """Take a key code from the HUD window (-1 means no key)."""
        if key < 0:
            return
        char = "esc" if key & 0xFF == ESC else chr(key & 0xFF).lower()
        if char in MOVE_KEYS:
            self._held_until[char] = self._clock() + HOLD_S
        else:
            self._pressed.add(char)

    def read(self) -> ManualInput:
        now = self._clock()
        held = {key for key, until in self._held_until.items() if until > now}
        pressed, self._pressed = self._pressed, set()
        return ManualInput(
            throttle=float(("w" in held) - ("s" in held)),
            steering=float(("d" in held) - ("a" in held)),
            toggle_mode="m" in pressed,
            emergency_stop=" " in pressed,
            quit=bool({"q", "esc"} & pressed),
        )

    def close(self) -> None:
        pass
