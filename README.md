# Air Paint - Рисование жестами

> Бейджи CI/Coverage будут добавлены после публикации репозитория на GitHub.

Приложение для рисования в воздухе (OpenCV + MediaPipe) с модульной архитектурой и расширяемым движком жестов.

Поддерживаются два режима:
- Desktop: классический OpenCV-UI (`airpaint`)
- Web: Python backend + браузерный frontend (`airpaint-web` + React Canvas)

## Демо

![demo](demo.gif)

Приложение компьютерного зрения использует:
- OpenCV
- MediaPipe
- Отслеживание руки в реальном времени
- Кастомный движок распознавания жестов

## Принципы архитектуры

- Модульный дизайн
- Контекстный менеджер для жизненного цикла камеры
- Реестр жестов (принцип Open/Closed)
- `RuntimeService` + протоколы зависимостей (`CameraLike`, `TrackerLike`, `PainterLike`) для тестируемости
- Алгоритм сглаживания в реальном времени
- Экспоненциальное сглаживание FPS

## Производительность

- ~30-60 FPS в зависимости от железа

## Возможности
- Рисование указательным пальцем
- Смена цвета жестом
- Очистка холста жестом
- Undo (жест + горячая клавиша)
- Сохранение снимка в PNG (жест + горячая клавиша)
- Изменение толщины кисти (жест)
- Алгоритм сглаживания
- Мониторинг FPS
- Система cooldown для жестов
- Независимый cooldown для каждого жеста (один жест не блокирует все остальные)
- HUD-оверлей (FPS / кисть / цвет)
- Сохранение объединенного кадра (как на экране)
- Настраиваемая карта жестов из JSON (`--gesture-map`)
- Temporal-gestures со state machine: `pinch-hold` (300ms), `swipe-left`, `double-tap`
- Live UI-подсказки рядом с рукой: распознанный жест и прогресс удержания (`pinch-hold 70%`)
- Shape assist: кривые контуры автоматически выравниваются в `circle` / `rectangle` / `arrow`
- Structured JSON logging + debug-метрики рантайма (`event=loop_stats`)
- Валидация CLI-аргументов с понятными ошибками диапазонов
- Web runtime: кадры из браузера -> backend распознает landmarks/жесты -> браузер рисует Canvas + HUD

## Структура проекта
airpaint/
configs/
tests/
web/

## Установка

pip install opencv-python mediapipe numpy
pip install -e .
pip install -r requirements-dev.txt  # для тестов и линтеров
pip install -r requirements-web.txt  # для web-backend

## Запуск

python -m airpaint 
airpaint

## Web версия (React + Canvas + WebSocket)

1) Запусти backend:

airpaint-web --host 0.0.0.0 --port 8000

2) Запусти frontend:

cd web
npm install
npm run dev

3) Открой `http://localhost:5173`.

Поток данных:
- Браузер берет кадры с вебкамеры (`getUserMedia`)
- Кадры отправляются в Python backend по WebSocket (`/ws/frames`)
- Backend возвращает landmarks/жесты + состояние холста
- React Canvas рисует линии и HUD в браузере

## Параметры CLI

airpaint --camera 0 --width 1280 --height 720 --cooldown 0.8 --snapshots-dir snapshots
airpaint --no-mirror
airpaint --gesture-map configs/gestures.example.json
airpaint --log-level DEBUG
airpaint --debug
airpaint --target-fps 60 --detect-every 3 --tracker-scale 0.6

## Roadmap (идеи)
- Поддержка headless/recording-режимов (на базе `RuntimeService`)
- Добавить режим "ластик" и простую палитру
- Упаковать как `pip install airpaint` (pyproject.toml)
- Реальный CI + coverage badge после публикации репозитория

## Управление

- **ESC / Q** - выход
- **C** - очистить холст
- **U** - undo
- **S** - сохранить снимок (PNG)

## Карта жестов (по умолчанию)

Формат пальцев: [thumb, index, middle, ring, pinky]

- **clear**:      [1, 1, 0, 0, 0]
- **color**:      [0, 1, 1, 0, 0]
- **undo**:       [1, 1, 1, 0, 0]
- **save**:       [0, 1, 1, 1, 0]
- **brush+**:     [1, 0, 0, 0, 1]
- **brush-**:     [1, 0, 0, 1, 1]

## Temporal gestures (по умолчанию)

- **pinch-hold (300ms)**: удержание pinсh (большой+указательный) -> `save`
- **swipe-left**: быстрый свайп указательным влево -> `undo`
- **double-tap**: два быстрых pinch-тапа -> `color`

## Кастомная карта жестов через JSON

Передай JSON-файл с переопределениями жестов:

```json
{
  "clear": [1, 1, 0, 0, 0],
  "undo": [1, 1, 1, 0, 0],
  "save": [0, 1, 1, 1, 0]
}
```

Допускаются только известные имена жестов, а пересечения паттернов валидируются до применения.

## Заметки для разработки

- Жесты регистрируются в `GestureController.register(...)`
- `Painter` поддерживает снимки состояния для undo в начале штриха
- Логи в structured JSON формате; для тюнинга включи `--debug` и смотри `event=loop_stats`
