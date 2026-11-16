"""Train the traffic sign detector: YOLO11n fine-tuned on a Roboflow dataset.

This is the training that produced models/traffic_signs_yolo11n.pt (May 2025),
rewritten from the original Colab notebook (legacy/colab_training.py) into small,
named steps. The car only needs the trained file; this script shows how it was made.

It needs a GPU. In Google Colab, clone the repo, store the key in Colab's
"Secrets" panel, and run:

    from google.colab import userdata
    import os
    os.environ["ROBOFLOW_API_KEY"] = userdata.get("ROBOFLOW_API_KEY")
    !pip install ultralytics roboflow
    !python training/train_detector.py

The Roboflow API key is read from the ROBOFLOW_API_KEY environment variable.
It is never written in the code.
"""

import os
import sys
from pathlib import Path

import yaml
from roboflow import Roboflow
from ultralytics import YOLO

# The dataset: 6 classes (Green_light, Red_light, crossing_sign, speed_40, speed_80, stop).
WORKSPACE = "proyect-34ynk"
PROJECT = "traffic_signs-xczln"
DATASET_VERSION = 6

# The exact settings stored inside the trained model file.
BASE_MODEL = "yolo11n.pt"  # the smallest YOLO11, pretrained on COCO; here it is fine-tuned
EPOCHS = 60
IMAGE_SIZE = 640
BATCH_SIZE = 16


def read_api_key() -> str:
    """The Roboflow key, from the environment. Stops with a clear message if it is missing."""
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        sys.exit("Set the ROBOFLOW_API_KEY environment variable first (see the docstring).")
    return api_key


def download_dataset(api_key: str) -> Path:
    """Download the dataset in YOLO format and return the path of its data.yaml."""
    project = Roboflow(api_key=api_key).workspace(WORKSPACE).project(PROJECT)
    dataset = project.version(DATASET_VERSION).download("yolov11")
    return Path(dataset.location) / "data.yaml"


def fix_split_paths(data_yaml: Path) -> None:
    """Point the train, validation and test splits at the folders next to data.yaml.

    Roboflow writes paths like ../train/images, which break depending on where the
    dataset was downloaded. This was the fix in the original notebook.
    """
    data = yaml.safe_load(data_yaml.read_text())
    data.update(train="./train/images", val="./valid/images", test="./test/images")
    data_yaml.write_text(yaml.safe_dump(data))


def train(data_yaml: Path) -> Path:
    """Fine-tune the base model and return the path of the best weights."""
    model = YOLO(BASE_MODEL)
    model.train(data=str(data_yaml), epochs=EPOCHS, imgsz=IMAGE_SIZE, batch=BATCH_SIZE)
    return Path(model.trainer.best)


def evaluate(weights: Path, data_yaml: Path) -> None:
    """Score the model on the test split, the images it never saw while training."""
    metrics = YOLO(weights).val(data=str(data_yaml), split="test")
    print(f"Test split: mAP50 = {metrics.box.map50:.3f}, mAP50-95 = {metrics.box.map:.3f}")


def main() -> None:
    data_yaml = download_dataset(read_api_key())
    fix_split_paths(data_yaml)
    best_weights = train(data_yaml)
    evaluate(best_weights, data_yaml)
    print(f"Done. Copy {best_weights} to models/traffic_signs_yolo11n.pt")


if __name__ == "__main__":
    main()
