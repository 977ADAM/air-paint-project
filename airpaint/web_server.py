from __future__ import annotations

import argparse
import json
from typing import Optional

from .logging_utils import setup_logging
from .web_runtime import WebRuntimeConfig, WebSessionRuntime

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = None
    WebSocket = None
    WebSocketDisconnect = Exception

try:
    import uvicorn
except ImportError:  # pragma: no cover - optional dependency
    uvicorn = None


def create_app(config: Optional[WebRuntimeConfig] = None):
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Install with: pip install -e .[web]")

    runtime_config = config or WebRuntimeConfig()
    app = FastAPI(title="AirPaint Web Backend", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/frames")
    async def ws_frames(websocket: WebSocket) -> None:
        await websocket.accept()
        session = WebSessionRuntime(runtime_config)

        await websocket.send_json(
            {
                "type": "ready",
                **session.snapshot_state(),
            }
        )

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "invalid_json"})
                    continue

                msg_type = message.get("type", "frame")
                request_id = message.get("id")

                if msg_type == "frame":
                    image_data = message.get("image")
                    if not isinstance(image_data, str):
                        payload = {
                            "type": "error",
                            "error": "missing_frame_image",
                        }
                    else:
                        try:
                            payload = {
                                "type": "result",
                                **session.process_base64_frame(image_data),
                            }
                        except ValueError as exc:
                            payload = {"type": "error", "error": str(exc)}
                elif msg_type == "command":
                    command = message.get("command")
                    if not isinstance(command, str):
                        payload = {"type": "error", "error": "missing_command"}
                    else:
                        try:
                            payload = {
                                "type": "command",
                                **session.handle_command(command, value=message.get("value")),
                            }
                        except ValueError as exc:
                            payload = {"type": "error", "error": str(exc)}
                else:
                    payload = {
                        "type": "error",
                        "error": f"unsupported_type:{msg_type}",
                    }

                if request_id is not None:
                    payload["id"] = request_id

                await websocket.send_json(payload)
        except WebSocketDisconnect:
            return
        finally:
            session.close()

    return app


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AirPaint Web backend")
    p.add_argument("--host", type=str, default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--max-hands", type=int, default=1)
    p.add_argument("--model-complexity", type=int, default=0, choices=[0, 1])
    p.add_argument("--tracker-scale", type=float, default=0.6)
    p.add_argument("--min-detection-confidence", type=float, default=0.5)
    p.add_argument("--min-tracking-confidence", type=float, default=0.5)
    p.add_argument("--cooldown", type=float, default=0.0)
    p.add_argument("--snapshots-dir", type=str, default="snapshots")
    p.add_argument("--gesture-map", type=str, default=None)
    p.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    setup_logging(args.log_level)

    if uvicorn is None:
        raise RuntimeError("uvicorn is not installed. Install with: pip install -e .[web]")

    config = WebRuntimeConfig(
        snapshots_dir=args.snapshots_dir,
        cooldown=float(args.cooldown),
        gesture_map=args.gesture_map,
        max_hands=int(args.max_hands),
        model_complexity=int(args.model_complexity),
        min_detection_confidence=float(args.min_detection_confidence),
        min_tracking_confidence=float(args.min_tracking_confidence),
        tracker_scale=float(args.tracker_scale),
    )

    app = create_app(config)
    uvicorn.run(
        app,
        host=args.host,
        port=int(args.port),
        log_level=str(args.log_level).lower(),
    )


if __name__ == "__main__":
    main()
