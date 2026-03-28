const { spawn } = require("child_process");
const path = require("path");
const { app } = require("electron");

/**
 * Manages communication with the Python OCR backend via stdio JSON-RPC.
 *
 * Protocol: newline-delimited JSON over stdin/stdout.
 * Request:  { "id": 1, "method": "start_ocr", "params": {...} }
 * Response: { "id": 1, "result": {...} }  or  { "id": 1, "error": "..." }
 * Event:    { "id": null, "event": "progress", "data": {...} }
 */
class PythonBridge {
  constructor() {
    this._process = null;
    this._requestId = 0;
    this._pending = new Map(); // id -> { resolve, reject, onProgress }
    this._buffer = "";

    this._spawn();
  }

  _getPythonPath() {
    // In production, Python scripts are in resources/python
    if (app.isPackaged) {
      return path.join(process.resourcesPath, "python", "bridge.py");
    }
    return path.join(__dirname, "../../src/ancient_pdf_master/bridge.py");
  }

  _findPython() {
    // Try common Python paths
    const candidates = ["python3", "python"];
    return candidates[0]; // Will be resolved by PATH
  }

  _spawn() {
    const scriptPath = this._getPythonPath();
    const python = this._findPython();

    this._process = spawn(python, ["-u", scriptPath], {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    this._process.stdout.on("data", (chunk) => {
      this._buffer += chunk.toString();
      this._processBuffer();
    });

    this._process.stderr.on("data", (chunk) => {
      console.error("[Python stderr]", chunk.toString());
    });

    this._process.on("exit", (code) => {
      console.log(`[Python] Process exited with code ${code}`);
      // Reject all pending requests
      for (const [id, handler] of this._pending) {
        handler.reject(new Error(`Python process exited (code ${code})`));
      }
      this._pending.clear();
    });
  }

  _processBuffer() {
    const lines = this._buffer.split("\n");
    // Keep incomplete last line in buffer
    this._buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        this._handleMessage(msg);
      } catch (e) {
        console.error("[Python] Invalid JSON:", line);
      }
    }
  }

  _handleMessage(msg) {
    // Progress event (no id)
    if (msg.event === "progress" && msg.data) {
      // Forward to all pending requests that have onProgress
      for (const handler of this._pending.values()) {
        if (handler.onProgress) handler.onProgress(msg.data);
      }
      return;
    }

    // Response to a request
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
   * @param {string} method
   * @param {object} params
   * @param {function} [onProgress] - optional progress callback
   * @returns {Promise<any>}
   */
  send(method, params, onProgress = null) {
    return new Promise((resolve, reject) => {
      if (!this._process || this._process.killed) {
        this._spawn();
      }

      const id = ++this._requestId;
      this._pending.set(id, { resolve, reject, onProgress });

      const request = JSON.stringify({ id, method, params }) + "\n";
      this._process.stdin.write(request);
    });
  }

  kill() {
    if (this._process && !this._process.killed) {
      this._process.kill();
      this._process = null;
    }
  }
}

module.exports = { PythonBridge };
