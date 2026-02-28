import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const FRAME_INTERVAL_MS = 90;
const CAPTURE_WIDTH = 480;
const CAPTURE_HEIGHT = 270;

function getDefaultWsUrl() {
  if (typeof window === "undefined") {
    return "ws://127.0.0.1:8000/ws/frames";
  }
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname || "127.0.0.1";
  return `${proto}://${host}:8000/ws/frames`;
}

function colorToCss(color) {
  if (!Array.isArray(color) || color.length !== 3) {
    return "rgb(255, 0, 255)";
  }
  return `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
}

function drawStrokes(ctx, strokes, width, height) {
  if (!Array.isArray(strokes)) {
    return;
  }

  for (const stroke of strokes) {
    if (!stroke || !Array.isArray(stroke.points) || stroke.points.length === 0) {
      continue;
    }

    ctx.strokeStyle = colorToCss(stroke.color);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = Number(stroke.thickness || 5);

    ctx.beginPath();
    stroke.points.forEach((point, idx) => {
      const x = Number(point.x || 0) * width;
      const y = Number(point.y || 0) * height;
      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
  }
}

function drawLandmarks(ctx, landmarks, width, height) {
  if (!Array.isArray(landmarks)) {
    return;
  }

  ctx.fillStyle = "rgba(40, 243, 163, 0.9)";
  for (const lm of landmarks) {
    const x = Number(lm.x || 0) * width;
    const y = Number(lm.y || 0) * height;
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawPointer(ctx, pointer, width, height) {
  if (!pointer) {
    return;
  }

  const x = Number(pointer.x || 0) * width;
  const y = Number(pointer.y || 0) * height;
  const drawing = Boolean(pointer.drawing);

  ctx.beginPath();
  ctx.arc(x, y, drawing ? 11 : 7, 0, Math.PI * 2);
  ctx.strokeStyle = drawing ? "rgba(255, 196, 68, 0.95)" : "rgba(255, 255, 255, 0.85)";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawHud(ctx, payload) {
  const hud = payload?.hud || {};
  const feedback = payload?.feedback || null;
  const gesture = payload?.gesture || "-";

  ctx.save();
  ctx.fillStyle = "rgba(5, 13, 30, 0.74)";
  ctx.fillRect(14, 14, 260, 120);

  ctx.font = "600 15px 'Space Grotesk', 'Segoe UI', sans-serif";
  ctx.fillStyle = "#f6f4ef";
  ctx.fillText(`Gesture: ${gesture}`, 24, 40);
  ctx.fillText(`Brush: ${hud.brush_thickness ?? "-"}`, 24, 64);
  ctx.fillText(`Strokes: ${hud.stroke_count ?? "-"}`, 24, 88);

  const feedbackText = feedback
    ? `${feedback.label}${typeof feedback.progress === "number" ? ` ${Math.round(feedback.progress * 100)}%` : ""}`
    : "-";
  ctx.fillText(`Hint: ${feedbackText}`, 24, 112);

  ctx.fillStyle = colorToCss(hud.color);
  ctx.fillRect(184, 50, 70, 24);
  ctx.strokeStyle = "rgba(246, 244, 239, 0.8)";
  ctx.strokeRect(184, 50, 70, 24);
  ctx.restore();
}

function App() {
  const defaultWsUrl = useMemo(getDefaultWsUrl, []);
  const [wsUrl, setWsUrl] = useState(defaultWsUrl);
  const [wsUrlDraft, setWsUrlDraft] = useState(defaultWsUrl);

  const [status, setStatus] = useState("connecting");
  const [error, setError] = useState("");
  const [lastGesture, setLastGesture] = useState("-");
  const [feedbackText, setFeedbackText] = useState("-");
  const [latencyMs, setLatencyMs] = useState(null);
  const [hud, setHud] = useState({ color: [255, 0, 255], brush_thickness: 5, stroke_count: 0, revision: 0 });

  const videoRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const stageCanvasRef = useRef(null);

  const socketRef = useRef(null);
  const requestCounterRef = useRef(0);
  const pendingFramesRef = useRef(new Map());
  const latestPayloadRef = useRef({ canvas: { strokes: [] }, hud: {} });

  const renderScene = useCallback(() => {
    const canvas = stageCanvasRef.current;
    if (!canvas) {
      return;
    }

    const ctx = canvas.getContext("2d");
    const payload = latestPayloadRef.current || {};
    const video = videoRef.current;

    const width = Number(video?.videoWidth || payload?.frame?.width || 960);
    const height = Number(video?.videoHeight || payload?.frame?.height || 540);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    if (video && video.readyState >= 2) {
      ctx.drawImage(video, 0, 0, width, height);
    } else {
      const gradient = ctx.createLinearGradient(0, 0, width, height);
      gradient.addColorStop(0, "#1d2840");
      gradient.addColorStop(1, "#0c1628");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);
    }

    drawStrokes(ctx, payload?.canvas?.strokes || [], width, height);
    drawLandmarks(ctx, payload?.landmarks || [], width, height);
    drawPointer(ctx, payload?.pointer, width, height);
    drawHud(ctx, payload);
  }, []);

  useEffect(() => {
    let rafId = 0;
    const loop = () => {
      renderScene();
      rafId = window.requestAnimationFrame(loop);
    };
    loop();

    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, [renderScene]);

  useEffect(() => {
    let mediaStream;
    let cancelled = false;

    async function openCamera() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 }
          },
          audio: false
        });
        if (cancelled) {
          mediaStream.getTracks().forEach((track) => track.stop());
          return;
        }

        const video = videoRef.current;
        if (!video) {
          return;
        }

        video.srcObject = mediaStream;
        await video.play();
      } catch (err) {
        setError(`Camera access failed: ${String(err.message || err)}`);
      }
    }

    openCamera();

    return () => {
      cancelled = true;
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  useEffect(() => {
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    setStatus("connecting");
    setError("");

    socket.onopen = () => {
      setStatus("connected");
    };

    socket.onclose = () => {
      setStatus("disconnected");
    };

    socket.onerror = () => {
      setError("WebSocket transport error");
    };

    socket.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (_e) {
        setError("Server returned invalid JSON");
        return;
      }

      if (payload?.id && pendingFramesRef.current.has(payload.id)) {
        const startedAt = pendingFramesRef.current.get(payload.id);
        pendingFramesRef.current.delete(payload.id);
        if (typeof startedAt === "number") {
          setLatencyMs(Math.max(0, Math.round(performance.now() - startedAt)));
        }
      }

      if (payload.type === "error") {
        setError(String(payload.error || "unknown_error"));
        return;
      }

      if (payload.hud) {
        setHud(payload.hud);
      }
      if (payload.gesture) {
        setLastGesture(String(payload.gesture));
      }
      if (payload.feedback) {
        const text = `${payload.feedback.label}${
          typeof payload.feedback.progress === "number"
            ? ` ${Math.round(payload.feedback.progress * 100)}%`
            : ""
        }`;
        setFeedbackText(text);
      }

      latestPayloadRef.current = payload;
      setError("");
    };

    return () => {
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      socket.close();
    };
  }, [wsUrl]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const socket = socketRef.current;
      const video = videoRef.current;
      const captureCanvas = captureCanvasRef.current;

      if (!socket || socket.readyState !== WebSocket.OPEN || !video || video.readyState < 2 || !captureCanvas) {
        return;
      }

      captureCanvas.width = CAPTURE_WIDTH;
      captureCanvas.height = CAPTURE_HEIGHT;

      const capCtx = captureCanvas.getContext("2d");
      capCtx.drawImage(video, 0, 0, CAPTURE_WIDTH, CAPTURE_HEIGHT);

      const image = captureCanvas.toDataURL("image/jpeg", 0.7);
      const id = `frame-${++requestCounterRef.current}`;
      pendingFramesRef.current.set(id, performance.now());
      if (pendingFramesRef.current.size > 20) {
        const staleKey = pendingFramesRef.current.keys().next().value;
        pendingFramesRef.current.delete(staleKey);
      }

      socket.send(
        JSON.stringify({
          type: "frame",
          id,
          image
        })
      );
    }, FRAME_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const sendCommand = useCallback((command, value) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    const id = `cmd-${++requestCounterRef.current}`;
    socket.send(JSON.stringify({ type: "command", id, command, value }));
  }, []);

  const isConnected = status === "connected";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">AirPaint</p>
          <h1>Browser Canvas + Python Gesture Backend</h1>
        </div>
        <form
          className="ws-form"
          onSubmit={(event) => {
            event.preventDefault();
            setWsUrl(wsUrlDraft.trim());
          }}
        >
          <label htmlFor="ws-url">WebSocket URL</label>
          <div>
            <input
              id="ws-url"
              type="text"
              value={wsUrlDraft}
              onChange={(event) => setWsUrlDraft(event.target.value)}
            />
            <button type="submit">Connect</button>
          </div>
        </form>
      </header>

      <main className="layout">
        <section className="stage-card">
          <canvas ref={stageCanvasRef} className="stage-canvas" />
          <video ref={videoRef} className="hidden-media" muted playsInline />
          <canvas ref={captureCanvasRef} className="hidden-media" />
        </section>

        <aside className="control-card">
          <div className="status-grid">
            <p>
              Status
              <strong className={`status-pill status-${status}`}>{status}</strong>
            </p>
            <p>
              Gesture
              <strong>{lastGesture}</strong>
            </p>
            <p>
              Hint
              <strong>{feedbackText}</strong>
            </p>
            <p>
              Latency
              <strong>{latencyMs === null ? "-" : `${latencyMs} ms`}</strong>
            </p>
          </div>

          <div className="hud-grid">
            <p>
              Brush
              <strong>{hud.brush_thickness}</strong>
            </p>
            <p>
              Strokes
              <strong>{hud.stroke_count}</strong>
            </p>
            <p>
              Revision
              <strong>{hud.revision}</strong>
            </p>
            <p>
              Color
              <strong style={{ color: colorToCss(hud.color) }}>{colorToCss(hud.color)}</strong>
            </p>
          </div>

          <div className="button-grid">
            <button disabled={!isConnected} onClick={() => sendCommand("clear")}>
              Clear
            </button>
            <button disabled={!isConnected} onClick={() => sendCommand("undo")}>
              Undo
            </button>
            <button disabled={!isConnected} onClick={() => sendCommand("save")}>
              Save JSON
            </button>
            <button disabled={!isConnected} onClick={() => sendCommand("color-next")}>
              Next Color
            </button>
            <button disabled={!isConnected} onClick={() => sendCommand("brush-plus")}>
              Brush +
            </button>
            <button disabled={!isConnected} onClick={() => sendCommand("brush-minus")}>
              Brush -
            </button>
          </div>

          <p className="error-line">{error || " "}</p>
        </aside>
      </main>
    </div>
  );
}

export default App;
