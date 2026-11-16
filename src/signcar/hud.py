"""The HUD: what the car sees and decides, drawn on top of the camera frame.

- Boxes: green when the filter trusts them, gray when it ignores them,
  labeled with the sign and the model's confidence.
- Top-left panel: mode, autopilot state, confirmed signs, vision and controller health.
- Bottom-right: one bar per side of the car (up = forward, down = reverse).

HudWindow shows the result in a window and/or records it to a video file.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from signcar.autopilot import AutopilotState
from signcar.camera import Frame
from signcar.driving import DriveCommand, Mode
from signcar.signs import Detection, Sign

# Colors are (blue, green, red): OpenCV's order.
GREEN = (80, 200, 80)
GRAY = (160, 160, 160)
WHITE = (240, 240, 240)
RED = (60, 60, 230)
ORANGE = (40, 150, 240)
BLUE = (230, 160, 60)
MODE_COLORS = {Mode.MANUAL: BLUE, Mode.AUTO: GREEN, Mode.EMERGENCY_STOP: RED}

FONT = cv2.FONT_HERSHEY_SIMPLEX
LINE_HEIGHT = 20
PANEL_WIDTH = 300
BAR_WIDTH = 16
BAR_HALF_HEIGHT = 50  # a bar grows this many pixels at full speed
MARGIN = 12


@dataclass(frozen=True)
class HudStatus:
    """Everything the panel and the bars show, besides the detections."""

    mode: Mode
    autopilot_state: AutopilotState
    command: DriveCommand
    confirmed: frozenset[Sign]
    vision_fps: float
    vision_fresh: bool
    controller_connected: bool


def draw_hud(
    frame: Frame,
    detections: list[Detection],
    is_trusted: Callable[[Detection], bool],
    status: HudStatus,
) -> Frame:
    """Return a copy of the frame with the HUD drawn on it. The original is not changed."""
    canvas = frame.copy()
    for detection in detections:
        _draw_detection(canvas, detection, trusted=is_trusted(detection))
    _draw_panel(canvas, status)
    _draw_wheel_bars(canvas, status.command)
    return canvas


def _draw_detection(canvas: Frame, detection: Detection, trusted: bool) -> None:
    height, width = canvas.shape[:2]
    box = detection.box
    top_left = (int(box.left * width), int(box.top * height))
    bottom_right = (int(box.right * width), int(box.bottom * height))
    color = GREEN if trusted else GRAY
    cv2.rectangle(canvas, top_left, bottom_right, color, 2)
    label = f"{detection.sign.value} {detection.confidence:.2f}"
    label_x, label_y = top_left[0], max(LINE_HEIGHT, top_left[1] - 6)
    # A black strip behind the label keeps it readable on bright images.
    (text_width, text_height), _ = cv2.getTextSize(label, FONT, 0.5, 1)
    strip_top_left = (label_x, label_y - text_height - 3)
    strip_bottom_right = (label_x + text_width + 4, label_y + 3)
    cv2.rectangle(canvas, strip_top_left, strip_bottom_right, (0, 0, 0), -1)
    cv2.putText(canvas, label, (label_x + 2, label_y), FONT, 0.5, color, 1, cv2.LINE_AA)


def _draw_panel(canvas: Frame, status: HudStatus) -> None:
    signs = ", ".join(sorted(sign.value for sign in status.confirmed)) or "-"
    vision = f"{status.vision_fps:.1f} fps" if status.vision_fresh else "LOST"
    controller_ok = status.controller_connected
    lines = [
        (f"MODE  {status.mode.value.upper()}", MODE_COLORS[status.mode]),
        (f"AUTOPILOT  {status.autopilot_state.value}", WHITE),
        (f"SIGNS  {signs}", WHITE),
        (f"VISION  {vision}", WHITE if status.vision_fresh else RED),
        (f"CONTROLLER  {'ok' if controller_ok else 'LOST'}", WHITE if controller_ok else RED),
    ]
    # A translucent dark background, so the text is readable on any image.
    panel_height = MARGIN + LINE_HEIGHT * len(lines)
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, 0), (PANEL_WIDTH, panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, dst=canvas)
    for row, (text, color) in enumerate(lines, start=1):
        position = (8, LINE_HEIGHT * row)
        cv2.putText(canvas, text, position, FONT, 0.5, color, 1, cv2.LINE_AA)


def wheel_bar_x(canvas: Frame, side: str) -> int:
    """Left edge (in pixels) of the bar for the "left" or "right" side of the car."""
    width = canvas.shape[1]
    right_bar_x = width - MARGIN - BAR_WIDTH
    return right_bar_x if side == "right" else right_bar_x - BAR_WIDTH - 8


def wheel_bar_baseline(canvas: Frame) -> int:
    """The y (in pixels) of the zero line of both bars."""
    return canvas.shape[0] - MARGIN - BAR_HALF_HEIGHT


def _draw_wheel_bars(canvas: Frame, command: DriveCommand) -> None:
    baseline = wheel_bar_baseline(canvas)
    for side, speed in (("left", command.left), ("right", command.right)):
        x = wheel_bar_x(canvas, side)
        # The outline shows the full range, the filling the current speed.
        top, bottom = baseline - BAR_HALF_HEIGHT, baseline + BAR_HALF_HEIGHT
        cv2.rectangle(canvas, (x, top), (x + BAR_WIDTH, bottom), GRAY, 1)
        fill_end = baseline - int(speed * BAR_HALF_HEIGHT)
        if fill_end != baseline:
            color = GREEN if speed > 0 else ORANGE
            y1, y2 = sorted((baseline, fill_end))
            cv2.rectangle(canvas, (x + 2, y1), (x + BAR_WIDTH - 2, y2), color, -1)
        cv2.line(canvas, (x, baseline), (x + BAR_WIDTH, baseline), WHITE, 1)


class HudWindow:
    """Shows the HUD in a window and/or records it to a video file.

    show() also returns the key pressed in the window (-1 when none), which is how
    the keyboard drives the simulation.
    """

    def __init__(self, title: str, show: bool, record_path: Path | None, fps: float) -> None:
        self._title = title
        self._show = show
        self._record_path = record_path
        self._fps = fps
        self._writer = None  # created with the first frame, when its size is known
        self._video_size = (0, 0)  # (width, height) of the recording

    def show(self, canvas: Frame | None) -> int:
        if canvas is not None:
            if self._record_path is not None:
                self._record(canvas)
            if self._show:
                cv2.imshow(self._title, canvas)
        return cv2.waitKey(1) if self._show else -1

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
        if self._show:
            cv2.destroyWindow(self._title)

    def _record(self, canvas: Frame) -> None:
        height, width = canvas.shape[:2]
        if self._writer is None:
            self._record_path.parent.mkdir(parents=True, exist_ok=True)
            self._video_size = (width, height)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(
                str(self._record_path), fourcc, self._fps, (width, height)
            )
        # A video file has one size. Frames of another size (the black frame shown before
        # the camera starts, or a camera that ignored the requested resolution) are scaled.
        if (width, height) != self._video_size:
            canvas = cv2.resize(canvas, self._video_size)
        self._writer.write(canvas)


def blank_frame(width: int, height: int) -> Frame:
    """A black frame, for when there is no camera image yet."""
    return np.zeros((height, width, 3), dtype=np.uint8)
