"""The `signcar` command.

signcar                          on the car: Pi camera, real motors, gamepad
signcar --show                   ... plus the HUD window (with a screen or VNC)
signcar --record run.mp4         ... recording the HUD to a video
signcar --sim                    on a PC: webcam, simulated motors, keyboard, HUD window
signcar --sim --source clip.mp4  ... with a video instead of the webcam
signcar --sim --gamepad          ... with the real gamepad instead of the keyboard
signcar --test-motors            spin each side both ways (wheels in the air!)
signcar --probe-gamepad          print stick and button numbers for GamepadConfig
"""

import argparse
import contextlib
import logging
import signal
from pathlib import Path

from signcar import app
from signcar.camera import OpenCvCamera, PiCamera
from signcar.config import Config
from signcar.detector import SignDetector
from signcar.gamepad import Gamepad, probe
from signcar.hud import HudWindow
from signcar.keyboard import KeyboardControls
from signcar.motors import SimulatedMotors, Tb6612Motors, run_motor_test


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="signcar", description="A car that sees traffic signs and obeys them."
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help="run on a PC: webcam or video, simulated motors, keyboard and HUD window",
    )
    parser.add_argument(
        "--source", default="0", help="with --sim: webcam number or video file (default: 0)"
    )
    parser.add_argument("--gamepad", action="store_true", help="with --sim: drive with the gamepad")
    parser.add_argument("--show", action="store_true", help="show the HUD window")
    parser.add_argument("--record", type=Path, metavar="VIDEO", help="record the HUD (.mp4)")
    tools = parser.add_mutually_exclusive_group()
    tools.add_argument(
        "--test-motors", action="store_true", help="spin each side both ways and exit"
    )
    tools.add_argument(
        "--probe-gamepad", action="store_true", help="print gamepad axis and button numbers"
    )
    return parser.parse_args(argv)


def parse_source(text: str) -> int | str:
    """ "0" means webcam number 0; anything else is the path of a video file."""
    return int(text) if text.isdigit() else text


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    # `kill` and systemd stop programs with SIGTERM. Turning it into a normal exit
    # lets the `finally` blocks run, so the motors are stopped.
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    config = Config()

    if args.probe_gamepad:
        probe()
    elif args.test_motors:
        _test_motors(config)
    else:
        # Ctrl+C ends the program quietly: app.run has already stopped the motors.
        with contextlib.suppress(KeyboardInterrupt):
            _drive(args, config)


def _drive(args: argparse.Namespace, config: Config) -> None:
    vision = config.vision
    # The model first: it is the slowest part to start and the most likely to fail.
    logging.info("Loading the model...")
    detector = SignDetector(vision.model_path, vision.image_size)
    if args.sim:
        source = parse_source(args.source)
        camera = OpenCvCamera(source, vision.frame_width, vision.frame_height)
        controls = Gamepad(config.gamepad) if args.gamepad else KeyboardControls()
        motors = SimulatedMotors()
    else:
        camera = PiCamera(vision.frame_width, vision.frame_height)
        controls = Gamepad(config.gamepad)
        motors = Tb6612Motors(config.motors)

    show = args.sim or args.show
    window = None
    if show or args.record:
        window = HudWindow("traffic-sign-car", show, args.record, fps=app.HUD_FPS)
    app.run(config, camera, detector, motors, controls, window)


def _test_motors(config: Config) -> None:
    motors = Tb6612Motors(config.motors)
    try:
        run_motor_test(motors)
    finally:
        motors.close()


def _exit_on_sigterm(signum, frame) -> None:
    raise SystemExit(0)


if __name__ == "__main__":
    main()
