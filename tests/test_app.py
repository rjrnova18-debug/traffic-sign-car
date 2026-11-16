"""The vision thread and the control loop, wired to fakes instead of hardware."""

import pytest

from signcar.app import ControlLoop, Perception, VisionWorker, run, smooth_fps
from signcar.autopilot import AutopilotState
from signcar.config import AutopilotConfig, Config, DrivingConfig, FilterConfig
from signcar.driving import STOPPED, DriveCommand, ManualInput, Mode
from signcar.hud import blank_frame
from signcar.motors import SimulatedMotors
from signcar.signs import Box, Detection, Sign, SignFilter

CONFIG = Config(
    autopilot=AutopilotConfig(start_speed=0.6, stop_hold_s=5.0),
    driving=DrivingConfig(max_manual_speed=0.7, vision_timeout_s=1.0),
)
FRAME = blank_frame(64, 48)
NO_INPUT = ManualInput()
TOGGLE = ManualInput(toggle_mode=True)


class FakeControls:
    """Gives scripted inputs, then no input."""

    def __init__(self, *inputs: ManualInput, connected: bool = True) -> None:
        self._inputs = list(inputs)
        self.connected = connected
        self.closed = False

    def read(self) -> ManualInput:
        return self._inputs.pop(0) if self._inputs else NO_INPUT

    def close(self) -> None:
        self.closed = True


class FakeVision:
    def __init__(self) -> None:
        self.latest: Perception | None = None

    def see(self, signs: set[Sign], at: float) -> None:
        self.latest = Perception(FRAME, [], frozenset(signs), at, fps=8.0)


def make_loop(controls: FakeControls) -> tuple[ControlLoop, FakeVision, SimulatedMotors]:
    vision, motors = FakeVision(), SimulatedMotors()
    return ControlLoop(CONFIG, controls, motors, vision), vision, motors


class TestControlLoop:
    def test_starts_in_manual_mode_and_follows_the_sticks(self):
        loop, _, motors = make_loop(FakeControls(ManualInput(throttle=1)))
        loop.tick(now=0)
        assert loop.mode is Mode.MANUAL
        assert motors.command == DriveCommand(0.7, 0.7)

    def test_auto_mode_drives_at_the_autopilot_speed(self):
        loop, vision, motors = make_loop(FakeControls(TOGGLE))
        vision.see(set(), at=0)
        loop.tick(now=0.1)
        assert loop.mode is Mode.AUTO
        assert motors.command == DriveCommand(0.6, 0.6)

    def test_a_stop_sign_in_auto_mode_stops_the_car_for_the_hold(self):
        loop, vision, motors = make_loop(FakeControls(TOGGLE))
        vision.see({Sign.STOP}, at=0)
        loop.tick(now=0.1)
        assert motors.command == STOPPED
        vision.see(set(), at=5.0)  # a new frame after the 5 s hold
        loop.tick(now=5.1)
        assert motors.command == DriveCommand(0.6, 0.6)

    def test_signs_seen_in_manual_mode_do_not_reach_the_autopilot(self):
        loop, vision, _ = make_loop(FakeControls())
        vision.see({Sign.STOP}, at=0)
        loop.tick(now=0.1)
        assert loop.autopilot.state is AutopilotState.CRUISING

    def test_entering_auto_mode_resets_the_autopilot(self):
        loop, vision, _ = make_loop(FakeControls(TOGGLE, NO_INPUT, TOGGLE, TOGGLE))
        vision.see({Sign.RED_LIGHT}, at=0)
        loop.tick(now=0.1)  # auto: waits for green
        assert loop.autopilot.state is AutopilotState.WAITING_FOR_GREEN
        loop.tick(now=0.2)
        loop.tick(now=0.3)  # back to manual
        loop.tick(now=0.4)  # auto again
        assert loop.autopilot.state is AutopilotState.CRUISING

    def test_stale_vision_stops_auto_mode(self):
        loop, vision, motors = make_loop(FakeControls(TOGGLE))
        vision.see(set(), at=0)
        loop.tick(now=1.5)
        assert motors.command == STOPPED

    def test_auto_mode_without_any_frame_yet_stays_stopped(self):
        loop, _, motors = make_loop(FakeControls(TOGGLE))
        loop.tick(now=0)
        assert motors.command == STOPPED

    def test_a_lost_controller_stops_the_car_and_goes_to_manual(self):
        controls = FakeControls(TOGGLE)
        loop, vision, motors = make_loop(controls)
        vision.see(set(), at=0)
        loop.tick(now=0.1)
        controls.connected = False
        loop.tick(now=0.2)
        assert (loop.mode, motors.command) == (Mode.MANUAL, STOPPED)

    def test_quit_ends_the_loop(self):
        loop, _, _ = make_loop(FakeControls(ManualInput(quit=True)))
        assert loop.tick(now=0) is False

    def test_the_hud_status_reports_stale_vision(self):
        loop, vision, _ = make_loop(FakeControls())
        vision.see({Sign.SPEED_40}, at=0)
        loop.tick(now=0.1)
        assert loop.hud_status(vision.latest, now=0.1).vision_fresh is True
        assert loop.hud_status(vision.latest, now=2.0).vision_fresh is False


class FakeCamera:
    def __init__(self, frames: int) -> None:
        self.frames_left = frames
        self.closed = False

    def read(self):
        if self.frames_left == 0:
            return None
        self.frames_left -= 1
        return FRAME

    def close(self) -> None:
        self.closed = True


class StopSignDetector:
    def detect(self, frame):
        return [Detection(Sign.STOP, 0.95, Box(0.4, 0.3, 0.6, 0.7))]


class BrokenDetector:
    def detect(self, frame):
        raise RuntimeError("model crashed")


class StepClock:
    """A clock that moves 0.1 s forward every time it is read."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.1
        return self.now


class TestVisionWorker:
    def test_analyzes_frames_until_the_camera_stops(self):
        sign_filter = SignFilter(FilterConfig(window_frames=5, min_frames=3))
        worker = VisionWorker(FakeCamera(frames=3), StopSignDetector(), sign_filter, StepClock())
        worker.run()  # called directly: no thread needed to test it
        assert worker.latest.confirmed == {Sign.STOP}
        assert worker.latest.fps == pytest.approx(10)

    def test_an_error_in_the_model_ends_the_thread_quietly(self):
        worker = VisionWorker(FakeCamera(frames=3), BrokenDetector(), SignFilter(FilterConfig()))
        worker.run()  # does not raise
        assert worker.latest is None

    def test_a_stopped_worker_reads_no_frames(self):
        camera = FakeCamera(frames=3)
        worker = VisionWorker(camera, StopSignDetector(), SignFilter(FilterConfig()))
        worker.stop()
        worker.run()
        assert camera.frames_left == 3


def test_smooth_fps_starts_from_the_first_value_then_averages():
    assert smooth_fps(0, 10) == 10
    assert smooth_fps(10, 20) == pytest.approx(12)


def test_run_stops_the_motors_and_closes_everything_on_the_way_out():
    camera, motors = FakeCamera(frames=1000), SimulatedMotors()
    controls = FakeControls(ManualInput(throttle=1), ManualInput(throttle=1, quit=True))
    run(CONFIG, camera, StopSignDetector(), motors, controls)
    assert motors.command == STOPPED
    assert camera.closed and controls.closed
