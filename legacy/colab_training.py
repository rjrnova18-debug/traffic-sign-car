# Original Google Colab training script, kept as it was written (May 2025).
# The ONLY change: the Roboflow API key was replaced with a placeholder,
# so no secret ever enters the git history. The organized version is
# training/train_detector.py.

# **1.  Instalación de librerías necesarias 🛠️**
#!pip install roboflow ultralytics --quiet

# **2. Descarga de dataset personalizado desde Roboflow 🗂️**

from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")
project = rf.workspace("proyect-34ynk").project("traffic_signs-xczln")
version = project.version(6)
dataset = version.download("yolov11")

from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")
project = rf.workspace("proyect-34ynk").project("traffic_signs-xczln")
version = project.version(6)
dataset = version.download("yolov11")

from ultralytics import YOLO
model = YOLO("yolo11n.pt")

# **4. Entrenamiento del modelo personalizado 🤖🏋️**

import yaml

data_path = "/content/Traffic_Signs-6/data.yaml"

# Update data.yaml to reflect correct paths if necessary
with open(data_path, 'r') as f:
    data = yaml.safe_load(f)

# Update paths to be relative to the data.yaml file
data['train'] = './train/images'
data['val'] = './valid/images'
data['test'] = './test/images'


with open(data_path, 'w') as f:
    yaml.dump(data, f)

results = model.train(data=data_path,
                      epochs=60,
                      imgsz=640)


# 5. ¡A hacer predicciones! 🤖
# Cargamos el modelo ya entrenado
custom_model = YOLO("/content/runs/detect/train/weights/best.pt")
# Realizamos predicciones sobre algunas imágenes
res = custom_model("/content/Traffic_Signs-6/test/images")
