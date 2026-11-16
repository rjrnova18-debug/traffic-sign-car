"""What the car can see: signs, detections, and the filter that decides which ones to believe.

Pure Python: no camera, no OpenCV, no model. detector.py turns the model's output into
Detection objects; from there on, everything can be tested without hardware.
"""

from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum

from signcar.config import FilterConfig


class Sign(Enum):
    """The six classes of the trained model. Each value is the model's class name."""

    GREEN_LIGHT = "Green_light"
    RED_LIGHT = "Red_light"
    CROSSING = "crossing_sign"
    SPEED_40 = "speed_40"
    SPEED_80 = "speed_80"
    STOP = "stop"


@dataclass(frozen=True)
class Box:
    """Where a detection is, as fractions (0-1) of the frame's width and height.

    Fractions instead of pixels, so the rules don't change with the camera resolution.
    """

    left: float
    top: float
    right: float
    bottom: float

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class Detection:
    """One box the model found in one frame."""

    sign: Sign
    confidence: float  # 0-1: how sure the model is
    box: Box


class SignFilter:
    """Turns noisy per-frame detections into confirmed signs.

    A detection is *trusted* when it is confident enough and its box is big enough
    (the sign is close). A sign is *confirmed* when it has a trusted detection in at
    least `min_frames` of the last `window_frames` frames. One lucky frame is never
    enough: the model's most common mistake is a green light seen in the background.
    """

    def __init__(self, config: FilterConfig) -> None:
        self._config = config
        # One set per frame: the signs trusted in that frame. Old frames fall off the left.
        self._recent_frames: deque[set[Sign]] = deque(maxlen=config.window_frames)

    def is_trusted(self, detection: Detection) -> bool:
        """True when a single detection is believable on its own."""
        return (
            detection.confidence >= self._config.min_confidence
            and detection.box.height >= self._config.min_box_height
        )

    def update(self, detections: list[Detection]) -> set[Sign]:
        """Add one frame's detections and return the signs that are confirmed now."""
        self._recent_frames.append({d.sign for d in detections if self.is_trusted(d)})
        frames_with_sign = Counter(sign for frame in self._recent_frames for sign in frame)
        return {
            sign for sign, frames in frames_with_sign.items() if frames >= self._config.min_frames
        }

    def reset(self) -> None:
        """Forget every frame seen so far."""
        self._recent_frames.clear()
