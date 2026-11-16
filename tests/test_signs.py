import pytest

from signcar.config import FilterConfig
from signcar.signs import Box, Detection, Sign, SignFilter

# The class names stored inside models/traffic_signs_yolo11n.pt, in the model's order.
MODEL_CLASS_NAMES = ["Green_light", "Red_light", "crossing_sign", "speed_40", "speed_80", "stop"]


def detection(sign: Sign, confidence: float = 0.9, height: float = 0.2) -> Detection:
    """A detection centered in the frame with the given box height."""
    top = 0.5 - height / 2
    return Detection(sign, confidence, Box(left=0.4, top=top, right=0.6, bottom=top + height))


@pytest.fixture
def sign_filter() -> SignFilter:
    return SignFilter(FilterConfig(min_confidence=0.85, min_box_height=0.12))


def feed(sign_filter: SignFilter, frames: list[list[Detection]]) -> set[Sign]:
    """Feed several frames and return what is confirmed after the last one."""
    confirmed: set[Sign] = set()
    for frame in frames:
        confirmed = sign_filter.update(frame)
    return confirmed


def test_every_model_class_name_maps_to_a_sign():
    assert [Sign(name).value for name in MODEL_CLASS_NAMES] == MODEL_CLASS_NAMES
    assert len(Sign) == len(MODEL_CLASS_NAMES)


def test_box_height_is_bottom_minus_top():
    assert Box(left=0.1, top=0.2, right=0.3, bottom=0.5).height == pytest.approx(0.3)


class TestIsTrusted:
    def test_confidence_at_the_threshold_is_trusted(self, sign_filter):
        assert sign_filter.is_trusted(detection(Sign.STOP, confidence=0.85))

    def test_confidence_below_the_threshold_is_not_trusted(self, sign_filter):
        assert not sign_filter.is_trusted(detection(Sign.STOP, confidence=0.84))

    def test_a_far_away_sign_is_not_trusted(self, sign_filter):
        assert not sign_filter.is_trusted(detection(Sign.STOP, height=0.05))


class TestUpdate:
    def test_one_frame_is_not_enough(self, sign_filter):
        assert sign_filter.update([detection(Sign.STOP)]) == set()

    def test_three_of_the_last_five_frames_confirm_a_sign(self, sign_filter):
        stop = [detection(Sign.STOP)]
        assert feed(sign_filter, [stop, [], stop, [], stop]) == {Sign.STOP}

    def test_a_sign_stops_being_confirmed_when_it_leaves_the_window(self, sign_filter):
        stop = [detection(Sign.STOP)]
        assert feed(sign_filter, [stop, stop, stop]) == {Sign.STOP}
        assert feed(sign_filter, [[], []]) == {Sign.STOP}  # still 3 of the last 5
        assert sign_filter.update([]) == set()  # now only 2 of the last 5

    def test_untrusted_detections_never_count(self, sign_filter):
        weak = [detection(Sign.GREEN_LIGHT, confidence=0.6)]
        assert feed(sign_filter, [weak] * 5) == set()

    def test_two_boxes_of_the_same_sign_count_as_one_frame(self, sign_filter):
        two_stops = [detection(Sign.STOP), detection(Sign.STOP)]
        assert feed(sign_filter, [two_stops, [], []]) == set()

    def test_several_signs_are_confirmed_independently(self, sign_filter):
        both = [detection(Sign.RED_LIGHT), detection(Sign.SPEED_40)]
        only_red = [detection(Sign.RED_LIGHT)]
        assert feed(sign_filter, [both, both, only_red]) == {Sign.RED_LIGHT}
        assert sign_filter.update(both) == {Sign.RED_LIGHT, Sign.SPEED_40}

    def test_reset_forgets_previous_frames(self, sign_filter):
        stop = [detection(Sign.STOP)]
        feed(sign_filter, [stop, stop])
        sign_filter.reset()
        assert sign_filter.update(stop) == set()


class TestFilterConfig:
    @pytest.mark.parametrize("confidence", [0, -0.1, 1.5])
    def test_rejects_a_confidence_outside_zero_to_one(self, confidence):
        with pytest.raises(ValueError):
            FilterConfig(min_confidence=confidence)

    def test_rejects_needing_more_frames_than_the_window(self):
        with pytest.raises(ValueError):
            FilterConfig(window_frames=3, min_frames=4)
