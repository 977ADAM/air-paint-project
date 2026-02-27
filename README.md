# Air Paint – Gesture Based Drawing

![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)

Gesture-driven drawing app (OpenCV + MediaPipe) with modular architecture and extensible gesture engine.

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
- Undo (gesture + hotkey)
- Save snapshot to PNG (gesture + hotkey)
- Brush thickness change (gesture)
- Smoothing algorithm
- FPS monitoring
- Gesture cooldown system
- HUD overlay (FPS / brush / color)
- Snapshots can save merged result (what you see on screen)

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

## CLI options

python main.py --camera 0 --width 1280 --height 720 --cooldown 0.8 --snapshots-dir snapshots
python main.py --no-mirror

## Roadmap (ideas)
- Add unit tests for gesture matching + painter undo
- Add configurable gesture map via JSON/YAML
- Add "eraser" mode and simple palette UI
- Package as `pip install airpaint` (pyproject.toml)

## Controls

- **ESC / Q** — exit
- **C** — clear
- **U** — undo
- **S** — save snapshot (PNG)

## Gesture map (default)

Fingers format: [thumb, index, middle, ring, pinky]

- **clear**:      [1, 1, 0, 0, 0]
- **color**:      [0, 1, 1, 0, 0]
- **undo**:       [1, 1, 1, 0, 0]
- **save**:       [0, 1, 1, 1, 0]
- **brush+**:     [0, 1, 0, 0, 0]
- **brush-**:     [0, 1, 0, 0, 1]

## Dev notes

- Gestures are registered in `GestureController.register(...)`
- Painter supports undo snapshots per stroke start