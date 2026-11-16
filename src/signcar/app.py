"""Runs the car: one thread looks, the main loop drives.

    camera ──▶ VisionWorker (thread): detect ─▶ filter ─▶ latest Perception
                                                                │
    gamepad / keyboard ──▶ ControlLoop (50 times a second) ◀────┘
                              mode ─▶ autopilot ─▶ fail-safe ─▶ motors

Why two loops: the model needs 50-80 ms per frame on a laptop CPU (more on the Pi),
but the controls must answer within ~20 ms. The control loop never waits for the model:
it uses the latest result, and the fail-safe stops auto mode if that result gets too old.
"""

import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from signcar.autopilot import Autopilot
from signcar.camera import Camera, Frame
from signcar.config import Config
from signcar.driving import STOPPED, ManualInput, Mode, choose_command, next_mode
from signcar.hud import HudStatus, HudWindow, blank_frame, draw_hud
from signcar.keyboard import KeyboardControls
from signcar.motors import Motors
from signcar.signs import Detection, Sign, SignFilter

log = logging.getLogger(__name__)

HUD_FPS = 10  # the HUD is redrawn (and recorded) 10 times a second


class Controls(Protocol):
    """The gamepad, or the keyboard in the simulation."""

    connected: bool

    def read(self) -> ManualInput: ...

    def close(self) -> None: ...


class Detector(Protocol):
    def detect(self, frame: Frame) -> list[Detection]: ...


@dataclass(frozen=True)
class Perception:
    """One analyzed frame: what the vision thread hands over to the control loop."""

    frame: Frame
    detections: list[Detection]
    confirmed: frozenset[Sign]
    time: float  # when the analysis finished, in time.monotonic() seconds
    fps: float  # frames analyzed per second, smoothed


class VisionWorker(threading.Thread):
    """Reads the camera and runs the model in the background, as fast as it can."""

    def __init__(
        self,
        camera: Camera,
        detector: Detector,
        sign_filter: SignFilter,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(name="vision", daemon=True)
        self._camera = camera
        self._detector = detector
        self._sign_filter = sign_filter
        self._clock = clock
        self._lock = threading.Lock()  # the control loop reads `latest` from another thread
        self._latest: Perception | None = None
        self._stopping = threading.Event()

    @property
    def latest(self) -> Perception | None:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._stopping.set()

    def run(self) -> None:
        try:
            self._analyze_frames()
        except Exception:
            # The car must never crash because of the vision. Without fresh results the
            # fail-safe stops auto mode, and manual driving keeps working.
            log.exception("The vision stopped because of an error")

    def _analyze_frames(self) -> None:
        fps = 0.0
        previous_time = None
        while not self._stopping.is_set():
            frame = self._camera.read()
            if frame is None:
                log.warning("The camera stopped giving frames")
                return
            detections = self._detector.detect(frame)
            confirmed = frozenset(self._sign_filter.update(detections))
            now = self._clock()
            if previous_time is not None and now > previous_time:
                fps = smooth_fps(fps, 1 / (now - previous_time))
            previous_time = now
            with self._lock:
                self._latest = Perception(frame, detections, confirmed, now, fps)


def smooth_fps(previous: float, current: float) -> float:
    """Average the frame rate over the last few frames, so the HUD number does not jump."""
    return current if previous == 0 else 0.8 * previous + 0.2 * current


class VisionSource(Protocol):
    @property
    def latest(self) -> Perception | None: ...


class ControlLoop:
    """One decision per tick: read the controls, choose the mode and the speed, drive."""

    def __init__(
        self, config: Config, controls: Controls, motors: Motors, vision: VisionSource
    ) -> None:
        self._config = config
        self._controls = controls
        self._motors = motors
        self._vision = vision
        self.mode = Mode.MANUAL
        self.autopilot = Autopilot(config.autopilot)
        self.command = STOPPED
        self._last_perception_time: float | None = None

    def tick(self, now: float) -> bool:
        """Run one control step. Returns False when the operator asks to quit."""
        manual = self._controls.read()
        connected = self._controls.connected
        self._update_mode(manual, connected)
        perception = self._vision.latest
        self._update_autopilot(perception)
        self.command = choose_command(
            self.mode,
            manual,
            self.autopilot.speed,
            controller_connected=connected,
            vision_age_s=vision_age(perception, now),
            config=self._config.driving,
        )
        self._motors.drive(self.command)
        return not manual.quit

    def hud_status(self, perception: Perception | None, now: float) -> HudStatus:
        return HudStatus(
            mode=self.mode,
            autopilot_state=self.autopilot.state,
            command=self.command,
            confirmed=perception.confirmed if perception else frozenset(),
            vision_fps=perception.fps if perception else 0.0,
            vision_fresh=vision_age(perception, now) <= self._config.driving.vision_timeout_s,
            controller_connected=self._controls.connected,
        )

    def _update_mode(self, manual: ManualInput, connected: bool) -> None:
        previous = self.mode
        self.mode = next_mode(previous, manual, controller_connected=connected)
        if self.mode is previous:
            return
        log.info("Mode: %s -> %s", previous.value, self.mode.value)
        if self.mode is Mode.AUTO:
            self.autopilot.reset()  # auto mode always starts fresh

    def _update_autopilot(self, perception: Perception | None) -> None:
        """Feed each new perception to the autopilot once, and only in auto mode."""
        if perception is None or perception.time == self._last_perception_time:
            return
        self._last_perception_time = perception.time
        if self.mode is not Mode.AUTO:
            return
        previous = self.autopilot.state
        self.autopilot.update(set(perception.confirmed), perception.time)
        if self.autopilot.state is not previous:
            log.info("Autopilot: %s -> %s", previous.value, self.autopilot.state.value)


def vision_age(perception: Perception | None, now: float) -> float:
    """Seconds since the latest frame was analyzed (infinite before the first one)."""
    return math.inf if perception is None else now - perception.time


def run(
    config: Config,
    camera: Camera,
    detector: Detector,
    motors: Motors,
    controls: Controls,
    window: HudWindow | None = None,
) -> None:
    """Drive until the operator quits. The motors are always stopped on the way out."""
    sign_filter = SignFilter(config.sign_filter)
    vision = VisionWorker(camera, detector, sign_filter)
    loop = ControlLoop(config, controls, motors, vision)
    tick_s = 1 / config.driving.control_rate_hz
    next_hud_time = 0.0

    vision.start()
    log.info("Running in manual mode")
    try:
        next_tick = time.monotonic()
        while loop.tick(now := time.monotonic()):
            if window is not None:
                canvas = None
                if now >= next_hud_time:
                    next_hud_time = now + 1 / HUD_FPS
                    canvas = hud_frame(loop, vision.latest, sign_filter, config, now)
                key = window.show(canvas)
                if isinstance(controls, KeyboardControls):
                    controls.handle_key(key)
            next_tick += tick_s
            time.sleep(max(0.0, next_tick - time.monotonic()))
    finally:
        motors.close()
        vision.stop()
        vision.join(timeout=2)
        camera.close()
        controls.close()
        if window is not None:
            window.close()
        log.info("Stopped")


def hud_frame(
    loop: ControlLoop,
    perception: Perception | None,
    sign_filter: SignFilter,
    config: Config,
    now: float,
) -> Frame:
    """The latest camera frame with the HUD on it (a black frame before the first one)."""
    status = loop.hud_status(perception, now)
    if perception is None:
        frame = blank_frame(config.vision.frame_width, config.vision.frame_height)
        return draw_hud(frame, [], sign_filter.is_trusted, status)
    return draw_hud(perception.frame, perception.detections, sign_filter.is_trusted, status)
