"""The conversion from the model's raw output to Detections (no ultralytics needed)."""

import pytest

from signcar.detector import check_class_names, to_detections
from signcar.signs import Box, Detection, Sign

# The class names stored inside models/traffic_signs_yolo11n.pt.
MODEL_NAMES = {
    0: "Green_light",
    1: "Red_light",
    2: "crossing_sign",
    3: "speed_40",
    4: "speed_80",
    5: "stop",
}


def test_converts_each_box_into_a_detection():
    detections = to_detections(
        boxes=[[0.1, 0.2, 0.3, 0.6], [0.5, 0.5, 0.7, 0.9]],
        confidences=[0.91, 0.42],
        class_ids=[5.0, 1.0],  # the model gives class ids as floats
        class_names=MODEL_NAMES,
    )
    assert detections == [
        Detection(Sign.STOP, 0.91, Box(0.1, 0.2, 0.3, 0.6)),
        Detection(Sign.RED_LIGHT, 0.42, Box(0.5, 0.5, 0.7, 0.9)),
    ]


def test_no_boxes_means_no_detections():
    assert to_detections([], [], [], MODEL_NAMES) == []


def test_the_trained_model_classes_are_all_known():
    check_class_names(MODEL_NAMES)  # does not raise


def test_a_model_with_unknown_classes_is_rejected():
    with pytest.raises(ValueError, match="yield_sign"):
        check_class_names({**MODEL_NAMES, 6: "yield_sign"})
