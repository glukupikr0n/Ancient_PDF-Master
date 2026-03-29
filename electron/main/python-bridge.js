const { spawn, execFileSync } = require("child_process");
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

const REQUIRED_PACKAGES = [
  "pytesseract",
  "Pillow",
  "pdf2image",
  "pikepdf",
  "reportlab",
];

class PythonBridge {
  constructor() {
    this._process = null;
    this._requestId = 0;
    this._pending = new Map();
    this._buffer = "";
    this._ready = false;
    this._readyPromise = null;
    this._startupError = null;
    this._pythonPath = null; // cached python executable path

    this._init();
  }

  /**
   * Initialize: find Python, ensure packages, spawn bridge.
   */
  async _init() {
    this._pythonPath = this._findPython();
    this._readyPromise = this._ensurePackagesAndSpawn();
  }

  _venvPythonPath(venvDir) {
    if (process.platform === "win32") {
      return path.join(venvDir, "Scripts", "python.exe");
    }
    return path.join(venvDir, "bin", "python3");
  }

  _findPython() {
    const candidates = [];

    // 1. App-local venv (Application Support / AppData)
    this._appVenvDir = path.join(app.getPath("userData"), ".venv");
    candidates.push(this._venvPythonPath(this._appVenvDir));

    // 2. Project-local .venv (dev mode)
    const projectRoot = path.join(__dirname, "../..");
    const localVenv = path.join(projectRoot, ".venv");
    candidates.push(this._venvPythonPath(localVenv));

    // 3. Homebrew Python paths (macOS)
    if (process.platform === "darwin") {
      candidates.push("/opt/homebrew/bin/python3");
      candidates.push("/usr/local/bin/python3");
    }

    // 4. Common Linux paths
    if (process.platform === "linux") {
      candidates.push("/usr/bin/python3");
      candidates.push("/usr/local/bin/python3");
    }

    for (const p of candidates) {
      if (fs.existsSync(p)) {
        console.log(`[Python] Using: ${p}`);
        return p;
      }
    }

    console.log("[Python] Using: python3 (system)");
    return "python3";
  }

  /**
   * Get the pip executable next to the Python interpreter.
   * For venv: /path/to/.venv/bin/pip3
   */
  _findPip() {
    if (!this._pythonPath || this._pythonPath === "python3") {
      return "pip3";
    }
    const dir = path.dirname(this._pythonPath);
    if (process.platform === "win32") {
      const pip = path.join(dir, "pip3.exe");
      if (fs.existsSync(pip)) return pip;
      const pip2 = path.join(dir, "pip.exe");
      if (fs.existsSync(pip2)) return pip2;
    } else {
      const pip = path.join(dir, "pip3");
      if (fs.existsSync(pip)) return pip;
      const pip2 = path.join(dir, "pip");
      if (fs.existsSync(pip2)) return pip2;
    }
    return "pip3";
  }

  _getSrcPath() {
    if (app.isPackaged) {
      return path.join(process.resourcesPath, "python");
    }
    return path.join(__dirname, "../../src");
  }

  _getTessdataPrefix() {
    // Bundled tessdata contains .traineddata files directly.
    // TESSDATA_PREFIX should point to the directory containing .traineddata files.
    const candidates = [];
    if (app.isPackaged) {
      candidates.push(path.join(process.resourcesPath, "tessdata"));
    }
    // Dev mode: project_root/tessdata/
    candidates.push(path.join(__dirname, "../../tessdata"));

    for (const dir of candidates) {
      if (fs.existsSync(dir)) {
        console.log(`[Python] Bundled tessdata: ${dir}`);
        return dir;
      }
    }
    return "";
  }

  _getEnvPath() {
    const existing = process.env.PATH || "";
    const sep = process.platform === "win32" ? ";" : ":";
    const extraPaths = [];

    if (process.platform === "darwin") {
      extraPaths.push("/opt/homebrew/bin", "/usr/local/bin", "/opt/homebrew/sbin", "/usr/local/sbin");
    } else if (process.platform === "linux") {
      extraPaths.push("/usr/local/bin", "/usr/bin");
    }

    // Add venv bin to PATH so Tesseract and other tools are found
    if (this._pythonPath && this._pythonPath !== "python3") {
      const venvBin = path.dirname(this._pythonPath);
      if (!extraPaths.includes(venvBin)) {
        extraPaths.unshift(venvBin);
      }
    }

    const parts = existing.split(sep);
    for (const p of extraPaths) {
      if (!parts.includes(p)) {
        parts.unshift(p);
      }
    }
    return parts.join(sep);
  }

  _getBrewPrefix() {
    try {
      return execFileSync("brew", ["--prefix"], { encoding: "utf8" }).trim();
    } catch {
      if (fs.existsSync("/opt/homebrew")) return "/opt/homebrew";
      if (fs.existsSync("/usr/local/Cellar")) return "/usr/local";
      return null;
    }
  }

  /**
   * Check if required packages are installed, install them if not.
   * Auto-creates a venv in Application Support if packaged and none exists.
   * Then spawn the bridge process.
   */
  async _ensurePackagesAndSpawn() {
    const envPath = this._getEnvPath();
    const env = { ...process.env, PATH: envPath };

    // If packaged and no venv exists, create one
    if (app.isPackaged && this._appVenvDir && !fs.existsSync(this._appVenvDir)) {
      console.log("[Python] No venv found \u2014 creating in Application Support...");
      this._emitSetupProgress("Creating Python environment...");
      await this._createVenv(env);
      // Re-discover python after venv creation
      this._pythonPath = this._findPython();
    }

    const python = this._pythonPath;

    // Quick check: can Python import all required packages?
    const checkScript = REQUIRED_PACKAGES
      .map((p) => {
        const mod = p === "Pillow" ? "PIL" : p;
        return `__import__('${mod}')`;
      })
      .join("; ");

    let needsInstall = false;
    try {
      execFileSync(python, ["-c", checkScript], {
        env,
        timeout: 10000,
        stdio: "pipe",
      });
      console.log("[Python] All packages already installed");
    } catch {
      console.log("[Python] Missing packages \u2014 auto-installing...");
      needsInstall = true;
    }

    if (needsInstall) {
      this._emitSetupProgress("Installing Python packages...");
      await this._installPackages(env);
    }

    this._emitSetupProgress(null); // clear setup status
    return this._spawnBridge();
  }

  /**
   * Create a virtual environment in Application Support.
   */
  _createVenv(env) {
    return new Promise((resolve, reject) => {
      // Find system python3 for venv creation
      const systemPython = this._findSystemPython();
      console.log(`[Python] Creating venv with: ${systemPython} at ${this._appVenvDir}`);

      // Ensure parent dir exists
      const parentDir = path.dirname(this._appVenvDir);
      if (!fs.existsSync(parentDir)) {
        fs.mkdirSync(parentDir, { recursive: true });
      }

      const proc = spawn(systemPython, ["-m", "venv", this._appVenvDir], {
        env,
        stdio: ["ignore", "pipe", "pipe"],
        timeout: 60000,
      });

      let stderr = "";
      proc.stderr.on("data", (d) => { stderr += d.toString(); });

      proc.on("exit", (code) => {
        if (code === 0) {
          console.log("[Python] Venv created successfully");
          resolve();
        } else {
          console.error("[Python] Venv creation failed:", stderr);
          reject(new Error(`Failed to create Python venv: ${stderr.split("\n").pop()}`));
        }
      });

      proc.on("error", (err) => {
        reject(new Error(`Failed to run python3 for venv: ${err.message}`));
      });
    });
  }

  /**
   * Find a system Python 3 (not from a venv) for creating new venvs.
   */
  _findSystemPython() {
    const candidates = [];
    if (process.platform === "darwin") {
      candidates.push("/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3");
    } else if (process.platform === "linux") {
      candidates.push("/usr/bin/python3", "/usr/local/bin/python3");
    } else {
      candidates.push("python3", "python");
    }
    for (const p of candidates) {
      if (fs.existsSync(p)) return p;
    }
    return "python3";
  }

  /**
   * Emit a setup progress event to the renderer (for first-launch UI).
   */
  _emitSetupProgress(message) {
    this._setupMessage = message;
    // Will be picked up by the renderer via IPC if mainWindow is available
  }

  /**
   * Auto-install required Python packages via pip.
   */
  _installPackages(env) {
    return new Promise((resolve, reject) => {
      const pip = this._findPip();
      const brewPrefix = this._getBrewPrefix();

      // Set C flags for pikepdf/qpdf compilation
      const installEnv = { ...env };
      if (brewPrefix) {
        installEnv.CFLAGS = `-I${brewPrefix}/include`;
        installEnv.LDFLAGS = `-L${brewPrefix}/lib`;
        installEnv.CPPFLAGS = `-I${brewPrefix}/include`;
        installEnv.PKG_CONFIG_PATH = `${brewPrefix}/lib/pkgconfig`;
      }

      console.log(`[Python] Running: ${pip} install ${REQUIRED_PACKAGES.join(" ")}`);

      const proc = spawn(pip, ["install", ...REQUIRED_PACKAGES], {
        env: installEnv,
        stdio: ["ignore", "pipe", "pipe"],
        timeout: 120000,
      });

      let stdout = "";
      let stderr = "";
      proc.stdout.on("data", (d) => {
        stdout += d.toString();
      });
      proc.stderr.on("data", (d) => {
        stderr += d.toString();
      });

      proc.on("exit", (code) => {
        if (code === 0) {
          console.log("[Python] Packages installed successfully");
          resolve();
        } else {
          const lastLine = stderr.trim().split("\n").pop() || stdout.trim().split("\n").pop();
          console.error("[Python] pip install failed:", lastLine);
          // Don't reject \u2014 still try to spawn, bridge.py will report the exact missing packages
          resolve();
        }
      });

      proc.on("error", (err) => {
        console.error("[Python] pip not found:", err.message);
        resolve(); // still try to spawn
      });
    });
  }

  /**
   * Spawn the Python bridge process and wait for ready signal.
   */
  _spawnBridge() {
    return new Promise((resolve, reject) => {
      const python = this._pythonPath;
      const srcPath = this._getSrcPath();
      const envPath = this._getEnvPath();

      console.log(`[Python] Spawning bridge... PYTHONPATH: ${srcPath}`);

      this._ready = false;
      this._startupError = null;

      const timeout = setTimeout(() => {
        if (!this._ready) {
          const err = this._stderrBuffer
            ? `Python startup timeout. ${this._stderrBuffer.trim().split("\n").pop()}`
            : "Python backend did not start within 15 seconds";
          this._startupError = err;
          reject(new Error(err));
        }
      }, 15000);

      const spawnEnv = {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        PYTHONPATH: srcPath,
        PATH: envPath,
      };

      // Set TESSDATA_PREFIX to bundled tessdata so Tesseract finds
      // language packs without requiring system-wide installation
      const tessdataPrefix = this._getTessdataPrefix();
      if (tessdataPrefix) {
        spawnEnv.TESSDATA_PREFIX = tessdataPrefix;
      }

      this._process = spawn(python, ["-u", "-m", "ancient_pdf_master.bridge"], {
        stdio: ["pipe", "pipe", "pipe"],
        env: spawnEnv,
      });

      this._process.stdout.on("data", (chunk) => {
        this._buffer += chunk.toString();
        this._processLines((msg) => {
          // Handle ready signal
          if ("ready" in msg) {
            clearTimeout(timeout);
            if (msg.ready) {
              this._ready = true;
              console.log("[Python] Backend ready");
              resolve();
            } else {
              const err = msg.error || "Python backend initialization failed";
              console.error("[Python] Not ready:", err);
              this._startupError = err;
              reject(new Error(err));
            }
            return true; // consumed
          }
          return false;
        });
      });

      this._stderrBuffer = "";
      this._process.stderr.on("data", (chunk) => {
        const text = chunk.toString();
        this._stderrBuffer += text;
        console.error("[Python stderr]", text);
      });

      this._process.on("error", (err) => {
        console.error("[Python] Failed to start:", err.message);
        clearTimeout(timeout);
        const msg = `Failed to start Python: ${err.message}`;
        this._startupError = msg;
        reject(new Error(msg));
        for (const handler of this._pending.values()) {
          handler.reject(new Error(msg));
        }
        this._pending.clear();
      });

      this._process.on("exit", (code) => {
        console.log(`[Python] Process exited with code ${code}`);
        clearTimeout(timeout);
        const errorDetail = this._stderrBuffer.trim();
        const lastLine = errorDetail ? errorDetail.split("\n").pop() : "";

        if (!this._ready) {
          const msg = lastLine
            ? `Python failed to start: ${lastLine}`
            : `Python process exited (code ${code})`;
          this._startupError = msg;
          reject(new Error(msg));
        }

        for (const handler of this._pending.values()) {
          const msg = lastLine
            ? `Python error: ${lastLine}`
            : `Python process exited (code ${code})`;
          handler.reject(new Error(msg));
        }
        this._pending.clear();
      });
    });
  }

  _processLines(onMessage) {
    const lines = this._buffer.split("\n");
    this._buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        // Let caller handle special messages first
        if (onMessage && onMessage(msg)) continue;
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
   * Waits for Python to be ready (including auto-install) before sending.
   */
  async send(method, params, onProgress = null) {
    // Wait for init (package check + spawn) to complete
    await this._readyPromise;

    return new Promise((resolve, reject) => {
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
