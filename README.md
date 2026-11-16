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

## Run it (PC, for development)

```bash
python -m venv venv
source venv/Scripts/activate      # Windows (Git Bash). On macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check . && ruff format --check .
```

## License

[AGPL-3.0](LICENSE), because the model was trained and runs with [Ultralytics](https://github.com/ultralytics/ultralytics), which is AGPL-3.0.
