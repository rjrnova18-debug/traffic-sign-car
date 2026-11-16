"""The command-line options (running the car itself needs the camera and the model)."""

from pathlib import Path

import pytest

from signcar.__main__ import parse_args, parse_source


def test_no_options_means_driving_the_real_car():
    args = parse_args([])
    assert (args.sim, args.show, args.record, args.gamepad) == (False, False, None, False)


def test_simulation_with_a_video_and_a_recording():
    args = parse_args(["--sim", "--source", "clip.mp4", "--record", "out.mp4"])
    assert args.sim and args.source == "clip.mp4"
    assert args.record == Path("out.mp4")


def test_the_tools_cannot_be_combined():
    with pytest.raises(SystemExit):
        parse_args(["--test-motors", "--probe-gamepad"])


@pytest.mark.parametrize(("text", "source"), [("0", 0), ("1", 1), ("clip.mp4", "clip.mp4")])
def test_a_number_is_a_webcam_and_anything_else_a_video(text, source):
    assert parse_source(text) == source
