/**
 * Auto-update manager using electron-updater.
 *
 * Checks GitHub Releases for new versions and notifies the renderer
 * process of update status. On macOS, downloads the DMG and prompts
 * the user to install. Gracefully degrades in development mode.
 */

const { app, ipcMain } = require("electron");

let autoUpdater;
let mainWindow;
let updateAvailable = false;

/**
 * Initialize the auto-updater.
 * @param {BrowserWindow} win - The main window for sending IPC events.
 */
function initAutoUpdater(win) {
  mainWindow = win;

  // electron-updater is only available in packaged builds
  if (!app.isPackaged) {
    console.log("[Updater] Skipping auto-update in development mode");
    return;
  }

  try {
    autoUpdater = require("electron-updater").autoUpdater;
  } catch (err) {
    console.log("[Updater] electron-updater not available:", err.message);
    return;
  }

  // Verify app-update.yml exists before proceeding
  const path = require("path");
  const fs = require("fs");
  const updateConfigPath = path.join(process.resourcesPath, "app-update.yml");
  if (!fs.existsSync(updateConfigPath)) {
    console.log("[Updater] app-update.yml not found — skipping auto-update");
    console.log("[Updater] Expected at:", updateConfigPath);
    // Register IPC handlers that return graceful "unavailable" responses
    ipcMain.handle("updater-check", async () => ({ status: "unavailable", message: "Update config not found. Rebuild with electron-builder to enable." }));
    ipcMain.handle("updater-download", async () => ({ status: "unavailable" }));
    ipcMain.handle("updater-install", () => {});
    ipcMain.handle("updater-get-version", () => ({ version: app.getVersion() }));
    return;
  }

  // Don't auto-download — let the user decide
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  // ── Events ──

  autoUpdater.on("checking-for-update", () => {
    sendStatus("checking", "Checking for updates...");
  });

  autoUpdater.on("update-available", (info) => {
    updateAvailable = true;
    sendStatus("available", `Update available: v${info.version}`, {
      version: info.version,
      releaseNotes: info.releaseNotes || "",
      releaseDate: info.releaseDate || "",
    });
  });

  autoUpdater.on("update-not-available", (info) => {
    sendStatus("up-to-date", `v${info.version} — up to date`);
  });

  autoUpdater.on("download-progress", (progress) => {
    sendStatus("downloading", `Downloading update: ${Math.round(progress.percent)}%`, {
      percent: progress.percent,
      bytesPerSecond: progress.bytesPerSecond,
      transferred: progress.transferred,
      total: progress.total,
    });
  });

  autoUpdater.on("update-downloaded", (info) => {
    sendStatus("ready", `Update v${info.version} ready to install`, {
      version: info.version,
    });
  });

  autoUpdater.on("error", (err) => {
    // Don't show ENOENT or network errors to user — just log
    const msg = err.message || "";
    if (msg.includes("ENOENT") || msg.includes("net::") || msg.includes("ERR_CONNECTION")) {
      console.log("[Updater] Silenced error:", msg);
      return;
    }
    sendStatus("error", `Update error: ${msg}`);
  });

  // ── IPC handlers ──

  ipcMain.handle("updater-check", async () => {
    if (!autoUpdater) return { status: "unavailable" };
    try {
      const result = await autoUpdater.checkForUpdates();
      return { status: "ok", version: result?.updateInfo?.version };
    } catch (err) {
      return { status: "error", message: err.message };
    }
  });

  ipcMain.handle("updater-download", async () => {
    if (!autoUpdater || !updateAvailable) return { status: "no-update" };
    try {
      await autoUpdater.downloadUpdate();
      return { status: "downloading" };
    } catch (err) {
      return { status: "error", message: err.message };
    }
  });

  ipcMain.handle("updater-install", () => {
    if (!autoUpdater) return;
    // Force quit and install — isSilent=false, isForceRunAfter=true
    // This ensures the old app is fully replaced
    autoUpdater.quitAndInstall(true, true);
  });

  ipcMain.handle("updater-get-version", () => {
    return { version: app.getVersion() };
  });

  // Check for updates 3 seconds after launch
  setTimeout(() => {
    autoUpdater.checkForUpdates().catch(() => {});
  }, 3000);

  // Check every 4 hours
  setInterval(
    () => {
      autoUpdater.checkForUpdates().catch(() => {});
    },
    4 * 60 * 60 * 1000,
  );
}

function sendStatus(status, message, data = {}) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("updater-status", { status, message, ...data });
  }
}

module.exports = { initAutoUpdater };
