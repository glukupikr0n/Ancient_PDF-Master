const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const { app } = require("electron");

/**
 * Manages communication with the Python OCR backend via stdio JSON-RPC.
 *
 * Protocol: newline-delimited JSON over stdin/stdout.
 * Startup:  Python sends {"ready": true} or {"ready": false, "error": "..."}
 * Request:  { "id": 1, "method": "start_ocr", "params": {...} }
 * Response: { "id": 1, "result": {...} }  or  { "id": 1, "error": "..." }
 * Event:    { "id": null, "event": "progress", "data": {...} }
 */
class PythonBridge {
  constructor() {
    this._process = null;
    this._requestId = 0;
    this._pending = new Map();
    this._buffer = "";
    this._ready = false;
    this._readyPromise = null;
    this._startupError = null;

    this._spawn();
  }

  _findPython() {
    const candidates = [];

    // 1. ~/Library/Application Support/Ancient PDF Master/.venv
    const appSupportVenv = path.join(
      app.getPath("userData"),
      ".venv",
      "bin",
      "python3"
    );
    candidates.push(appSupportVenv);

    // 2. Project-local .venv (dev mode)
    const projectRoot = path.join(__dirname, "../..");
    const localVenv = path.join(projectRoot, ".venv", "bin", "python3");
    candidates.push(localVenv);

    // 3. Homebrew Python paths
    candidates.push("/opt/homebrew/bin/python3");
    candidates.push("/usr/local/bin/python3");

    for (const p of candidates) {
      if (fs.existsSync(p)) {
        console.log(`[Python] Using: ${p}`);
        return p;
      }
    }

    console.log("[Python] Using: python3 (system)");
    return "python3";
  }

  _getPythonPath() {
    if (app.isPackaged) {
      return path.join(process.resourcesPath, "python");
    }
    return path.join(__dirname, "../../src");
  }

  _getEnvPath() {
    const existing = process.env.PATH || "";
    const extraPaths = [
      "/opt/homebrew/bin",
      "/usr/local/bin",
      "/opt/homebrew/sbin",
      "/usr/local/sbin",
    ];
    const parts = existing.split(":");
    for (const p of extraPaths) {
      if (!parts.includes(p)) {
        parts.unshift(p);
      }
    }
    return parts.join(":");
  }

  _spawn() {
    const python = this._findPython();
    const pythonPath = this._getPythonPath();
    const envPath = this._getEnvPath();

    console.log(`[Python] PYTHONPATH: ${pythonPath}`);

    this._ready = false;
    this._startupError = null;

    // Create a promise that resolves when Python sends {"ready": true}
    this._readyPromise = new Promise((resolve, reject) => {
      this._readyResolve = resolve;
      this._readyReject = reject;
    });

    // Timeout: if Python doesn't send ready in 8 seconds, fail
    this._readyTimeout = setTimeout(() => {
      if (!this._ready) {
        const err = this._stderrBuffer
          ? `Python startup timeout. stderr: ${this._stderrBuffer.trim().split("\n").pop()}`
          : "Python backend did not start within 8 seconds";
        this._startupError = err;
        this._readyReject(new Error(err));
      }
    }, 8000);

    this._process = spawn(python, ["-u", "-m", "ancient_pdf_master.bridge"], {
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        PYTHONPATH: pythonPath,
        PATH: envPath,
      },
    });

    this._process.stdout.on("data", (chunk) => {
      this._buffer += chunk.toString();
      this._processBuffer();
    });

    this._stderrBuffer = "";
    this._process.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      this._stderrBuffer += text;
      console.error("[Python stderr]", text);
    });

    this._process.on("error", (err) => {
      console.error("[Python] Failed to start:", err.message);
      clearTimeout(this._readyTimeout);
      const msg = `Failed to start Python: ${err.message}`;
      this._startupError = msg;
      this._readyReject(new Error(msg));
      for (const [id, handler] of this._pending) {
        handler.reject(new Error(msg));
      }
      this._pending.clear();
    });

    this._process.on("exit", (code) => {
      console.log(`[Python] Process exited with code ${code}`);
      clearTimeout(this._readyTimeout);
      const errorDetail = this._stderrBuffer.trim();
      const lastLine = errorDetail ? errorDetail.split("\n").pop() : "";

      if (!this._ready) {
        const msg = lastLine
          ? `Python failed to start: ${lastLine}`
          : `Python process exited (code ${code})`;
        this._startupError = msg;
        this._readyReject(new Error(msg));
      }

      for (const [id, handler] of this._pending) {
        const msg = lastLine
          ? `Python error: ${lastLine}`
          : `Python process exited (code ${code})`;
        handler.reject(new Error(msg));
      }
      this._pending.clear();
    });
  }

  _processBuffer() {
    const lines = this._buffer.split("\n");
    this._buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);

        // Handle ready signal from Python
        if ("ready" in msg) {
          clearTimeout(this._readyTimeout);
          if (msg.ready) {
            this._ready = true;
            console.log("[Python] Backend ready");
            this._readyResolve();
          } else {
            const err = msg.error || "Python backend initialization failed";
            console.error("[Python] Not ready:", err);
            this._startupError = err;
            this._readyReject(new Error(err));
          }
          continue;
        }

        this._handleMessage(msg);
      } catch (e) {
        console.error("[Python] Invalid JSON:", line);
      }
    }
  }

  _handleMessage(msg) {
    if (msg.event === "progress" && msg.data) {
      for (const handler of this._pending.values()) {
        if (handler.onProgress) handler.onProgress(msg.data);
      }
      return;
    }

    if (msg.id != null && this._pending.has(msg.id)) {
      const handler = this._pending.get(msg.id);
      this._pending.delete(msg.id);

      if (msg.error) {
        handler.reject(new Error(msg.error));
      } else {
        handler.resolve(msg.result);
      }
    }
  }

  /**
   * Send a request to the Python backend.
   * Waits for Python to be ready before sending.
   */
  async send(method, params, onProgress = null) {
    if (!this._process || this._process.killed) {
      this._spawn();
    }

    // Wait for Python to be ready
    await this._readyPromise;

    return new Promise((resolve, reject) => {
      const id = ++this._requestId;
      this._pending.set(id, { resolve, reject, onProgress });

      const request = JSON.stringify({ id, method, params }) + "\n";
      this._process.stdin.write(request);
    });
  }

  kill() {
    clearTimeout(this._readyTimeout);
    if (this._process && !this._process.killed) {
      this._process.kill();
      this._process = null;
    }
  }
}

module.exports = { PythonBridge };
