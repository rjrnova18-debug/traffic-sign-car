"""Where the frames come from.

- PiCamera: the Raspberry Pi camera on the ribbon cable, through picamera2.
- OpenCvCamera: a webcam or a video file on a PC, through OpenCV.

Both give frames as OpenCV images (BGR arrays) from read(), or None when there is no
frame (the video ended or the camera failed), and both have close(). Each one imports
its library only when it is created, so the PC never needs picamera2.
"""

from typing import Any, Protocol

Frame = Any  # a numpy array of shape (height, width, 3), in BGR order


class Camera(Protocol):
    def read(self) -> Frame | None: ...

    def close(self) -> None: ...


class PiCamera:
    """The camera module of the car. On the Pi 5, OpenCV cannot open it directly."""

    def __init__(self, width: int, height: int) -> None:
        from picamera2 import Picamera2

        self._camera = Picamera2()
        # "RGB888" is libcamera's name for pixels stored B, G, R in memory: OpenCV's order.
        config = self._camera.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self._camera.configure(config)
        self._camera.start()

    def read(self) -> Frame | None:
        return self._camera.capture_array()

    def close(self) -> None:
        self._camera.stop()
        self._camera.close()


class OpenCvCamera:
    """A webcam (pass its number, usually 0) or a video file (pass its path)."""

    def __init__(self, source: int | str, width: int, height: int) -> None:
        import cv2

        self._capture = cv2.VideoCapture(source)
        if not self._capture.isOpened():
            raise RuntimeError(f"Cannot open the camera or video: {source}")
        if isinstance(source, int):
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            # Keep at most one frame waiting, so read() returns what the camera sees
            # now, not a frame that waited in a queue while the model was busy.
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self) -> Frame | None:
        ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        self._capture.release()
