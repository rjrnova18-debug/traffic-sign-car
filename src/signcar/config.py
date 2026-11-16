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
