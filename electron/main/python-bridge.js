const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");
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

  /**
   * Find the best Python interpreter.
   *
   * Search order:
   *   1. App Support venv (for packaged .app)
   *   2. Project-local .venv (for dev mode / npm start)
   *   3. Homebrew Python
   *   4. System python3
   */
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
    candidates.push("/opt/homebrew/bin/python3"); // Apple Silicon
    candidates.push("/usr/local/bin/python3"); // Intel Mac

    for (const p of candidates) {
      if (fs.existsSync(p)) {
        console.log(`[Python] Using: ${p}`);
        return p;
      }
    }

    // 4. Fallback
    console.log("[Python] Using: python3 (system)");
    return "python3";
  }

  /**
   * Get PYTHONPATH for the ancient_pdf_master package.
   *
   * - Packaged: Resources/python/ (contains ancient_pdf_master/)
   * - Dev mode: project/src/
   */
  _getPythonPath() {
    if (app.isPackaged) {
      return path.join(process.resourcesPath, "python");
    }
    return path.join(__dirname, "../../src");
  }

  /**
   * Build PATH that includes Homebrew so tesseract/poppler are found.
   * macOS .app bundles don't inherit the user's shell PATH.
   */
  _getEnvPath() {
    const existing = process.env.PATH || "";
    const extraPaths = [
      "/opt/homebrew/bin",     // Apple Silicon Homebrew
      "/usr/local/bin",        // Intel Homebrew
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
    console.log(`[Python] PATH includes Homebrew: ${envPath.includes("homebrew") || envPath.includes("/usr/local/bin")}`);

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
      for (const [id, handler] of this._pending) {
        handler.reject(new Error(`Failed to start Python: ${err.message}`));
      }
      this._pending.clear();
    });

    this._process.on("exit", (code) => {
      console.log(`[Python] Process exited with code ${code}`);
      const errorDetail = this._stderrBuffer.trim();
      for (const [id, handler] of this._pending) {
        const msg = errorDetail
          ? `Python backend error (code ${code}): ${errorDetail.split("\n").pop()}`
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
