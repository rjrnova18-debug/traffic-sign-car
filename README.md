# Traffic Sign Car

> 🚧 Work in progress.

A small four-wheel car with a **Raspberry Pi 5** and a camera that recognizes traffic signs with a **YOLO11n** model and obeys them:

| Sign | What the car does |
|---|---|
| Stop | Stops for 5 seconds, then drives on |
| Red light | Stops until it sees the green light |
| Speed limit 40 / 80 | Changes its cruise speed |
| Pedestrian crossing | Slows down for a few seconds |

A wireless gamepad drives it by hand and switches between manual and autonomous mode.

I built the car in May 2025, but the code that ran on the Pi was lost. This repo rebuilds it from what survived (the training script, the trained model and a motor test) and makes it sturdier: stronger filtering against false detections, fail-safe stops, a PC simulation, tests and CI. The surviving scripts are kept in [`legacy/`](legacy/).

## Run it on a PC (simulation)

The webcam replaces the car's camera, the motors are simulated (two bars in the HUD) and the keyboard replaces the gamepad. Hold a phone with pictures of signs in front of the webcam.

```bash
python -m venv venv
source venv/Scripts/activate      # Windows (Git Bash). On macOS/Linux: source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .                  # creates the `signcar` command
signcar --sim                     # or: signcar --sim --source video.mp4
```

| Key | Action |
|---|---|
| W / S | Forward / backward |
| A / D | Turn left / right |
| M | Manual ↔ auto |
| Space | Emergency stop (press again to release) |
| Q / Esc | Quit |

> On Windows, PyTorch needs [long paths enabled](https://pip.pypa.io/warnings/enable-long-paths) if the project lives in a deep folder.

## Run it on the car (Raspberry Pi 5)

```bash
git clone https://github.com/rjrnova18-debug/traffic-sign-car.git && cd traffic-sign-car
python3 -m venv --system-site-packages venv   # picamera2 and gpiozero come from Raspberry Pi OS
source venv/bin/activate
pip install -r requirements-pi.txt && pip install -e .

signcar --test-motors      # wheels in the air: each side spins both ways
signcar --probe-gamepad    # find your gamepad's stick and button numbers
signcar                    # drive (add --record run.mp4 to film the HUD)
```

## Tests

```bash
pytest
ruff check . && ruff format --check .
```

## License

[AGPL-3.0](LICENSE), because the model was trained and runs with [Ultralytics](https://github.com/ultralytics/ultralytics), which is AGPL-3.0.
