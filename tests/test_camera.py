"""OpenCvCamera, tested with a tiny video file written on the fly.

PiCamera needs the real camera module, so it is checked on the car.
"""

import cv2
import numpy as np
import pytest

from signcar.camera import OpenCvCamera


def write_video(path, frames: int, width: int = 64, height: int = 48) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (width, height))
    for shade in range(frames):
        writer.write(np.full((height, width, 3), shade * 40, dtype=np.uint8))
    writer.release()


def test_reads_every_frame_of_a_video_then_none(tmp_path):
    video = tmp_path / "clip.avi"
    write_video(video, frames=3)
    camera = OpenCvCamera(str(video), width=64, height=48)

    frames = [camera.read() for _ in range(4)]
    camera.close()

    assert [frame is not None for frame in frames] == [True, True, True, False]
    assert frames[0].shape == (48, 64, 3)


def test_a_missing_video_raises_a_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="Cannot open"):
        OpenCvCamera(str(tmp_path / "missing.avi"), width=64, height=48)
