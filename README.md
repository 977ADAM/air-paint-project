# Air Paint – Gesture Based Drawing

## Demo

![demo](demo.gif)


Computer vision drawing app using:
- OpenCV
- MediaPipe
- Real-time hand tracking
- Custom gesture recognition engine

## Architecture Principles

- Modular design
- Context manager for camera lifecycle
- Gesture registry (Open/Closed principle)
- Real-time smoothing algorithm
- FPS exponential smoothing

## Performance

- ~30-60 FPS depending on hardware

## Features
- Draw with index finger
- Change colors via gesture
- Clear canvas gesture
- Smoothing algorithm
- FPS monitoring
- Gesture cooldown system

## Architecture
camera.py
hand_tracker.py
gesture_controller.py
painter.py
main.py

## Install

pip install opencv-python mediapipe numpy

## Run

python main.py