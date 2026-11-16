"""Finds signs in a frame with the trained YOLO11n model.

The only module that knows about ultralytics. It turns the model's output into
Detection objects (signs.py), so nothing else depends on the model library.
ultralytics is imported only when a SignDetector is created, so the tests
(and the CI) never need it.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from signcar.camera import Frame
from signcar.signs import Box, Detection, Sign

# Low on purpose: weak boxes still reach the HUD (drawn in gray), and SignFilter
# is the one that decides what to believe (0.85).
MODEL_MIN_CONFIDENCE = 0.25


def check_class_names(class_names: Mapping[int, str]) -> None:
    """Fail at startup, with a clear message, if the model has classes the car does not know."""
    known = {sign.value for sign in Sign}
    unknown = sorted(set(class_names.values()) - known)
    if unknown:
        raise ValueError(f"The model has classes the car does not know: {unknown}")


def to_detections(
    boxes: Sequence[Sequence[float]],
    confidences: Sequence[float],
    class_ids: Sequence[float],
    class_names: Mapping[int, str],
) -> list[Detection]:
    """Build Detections from the model's raw output, given as plain lists.

    boxes: [left, top, right, bottom] of each detection, as fractions of the frame.
    class_names: the model's class names by id, e.g. {0: "Green_light", 1: "Red_light"}.
    """
    return [
        Detection(
            sign=Sign(class_names[int(class_id)]),
            confidence=float(confidence),
            box=Box(*(float(value) for value in box)),
        )
        for box, confidence, class_id in zip(boxes, confidences, class_ids, strict=True)
    ]


class SignDetector:
    def __init__(self, model_path: Path, image_size: int) -> None:
        from ultralytics import YOLO

        self._model = YOLO(str(model_path))
        self._image_size = image_size
        check_class_names(self._model.names)

    def detect(self, frame: Frame) -> list[Detection]:
        """Every sign the model sees in one frame, trusted or not."""
        result = self._model.predict(
            frame, imgsz=self._image_size, conf=MODEL_MIN_CONFIDENCE, verbose=False
        )[0]
        boxes = result.boxes
        return to_detections(
            boxes.xyxyn.tolist(), boxes.conf.tolist(), boxes.cls.tolist(), result.names
        )
