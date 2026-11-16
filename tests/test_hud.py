"""The HUD drawing, checked pixel by pixel on a black frame."""

import numpy as np
import pytest

from signcar.autopilot import AutopilotState
from signcar.driving import STOPPED, DriveCommand, Mode
from signcar.hud import (
    GRAY,
    GREEN,
    ORANGE,
    HudStatus,
    HudWindow,
    blank_frame,
    draw_hud,
    wheel_bar_baseline,
    wheel_bar_x,
)
from signcar.signs import Box, Detection, Sign

WIDTH, HEIGHT = 640, 480


def status(command: DriveCommand = STOPPED) -> HudStatus:
    return HudStatus(
        mode=Mode.AUTO,
        autopilot_state=AutopilotState.CRUISING,
        command=command,
        confirmed=frozenset({Sign.STOP}),
        vision_fps=7.5,
        vision_fresh=True,
        controller_connected=True,
    )


def color_at(canvas, x: int, y: int) -> tuple[int, ...]:
    return tuple(int(channel) for channel in canvas[y, x])


@pytest.fixture
def frame():
    return blank_frame(WIDTH, HEIGHT)


def test_returns_a_new_image_and_leaves_the_frame_untouched(frame):
    canvas = draw_hud(frame, [], lambda d: True, status())
    assert canvas.shape == frame.shape
    assert not frame.any()  # still all black
    assert canvas.any()  # the panel and the bars were drawn


@pytest.mark.parametrize(("trusted", "color"), [(True, GREEN), (False, GRAY)])
def test_boxes_are_green_when_trusted_and_gray_when_ignored(frame, trusted, color):
    stop = Detection(Sign.STOP, 0.9, Box(left=0.5, top=0.5, right=0.7, bottom=0.8))
    canvas = draw_hud(frame, [stop], lambda d: trusted, status())
    assert color_at(canvas, int(0.5 * WIDTH), int(0.5 * HEIGHT)) == color


@pytest.mark.parametrize(("speed", "offset", "color"), [(1.0, -20, GREEN), (-1.0, 20, ORANGE)])
def test_wheel_bars_grow_up_for_forward_and_down_for_reverse(frame, speed, offset, color):
    canvas = draw_hud(frame, [], lambda d: True, status(DriveCommand.straight(speed)))
    x = wheel_bar_x(canvas, "left") + 8
    assert color_at(canvas, x, wheel_bar_baseline(canvas) + offset) == color


def test_a_stopped_car_has_empty_bars(frame):
    canvas = draw_hud(frame, [], lambda d: True, status(STOPPED))
    x = wheel_bar_x(canvas, "right") + 8
    assert color_at(canvas, x, wheel_bar_baseline(canvas) - 20) == (0, 0, 0)


def test_the_window_records_frames_to_a_video(tmp_path, frame):
    video = tmp_path / "recordings" / "run.mp4"
    window = HudWindow("test", show=False, record_path=video, fps=10)
    for _ in range(3):
        assert window.show(frame) == -1  # no window, so no key
    window.close()
    assert video.stat().st_size > 0


def test_a_hidden_window_without_recording_does_nothing(frame):
    window = HudWindow("test", show=False, record_path=None, fps=10)
    assert window.show(np.zeros_like(frame)) == -1
    window.close()
