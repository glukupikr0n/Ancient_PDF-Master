const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const path = require("path");
const { PythonBridge } = require("./python-bridge");

let mainWindow;
let pythonBridge;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    minWidth: 700,
    minHeight: 550,
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: "#1a1a2e",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));

  if (process.argv.includes("--dev")) {
    mainWindow.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  pythonBridge = new PythonBridge();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (pythonBridge) pythonBridge.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (pythonBridge) pythonBridge.kill();
});

// ── IPC Handlers ──

ipcMain.handle("select-input-file", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Input File",
    filters: [
      {
        name: "Supported Files",
        extensions: ["pdf", "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"],
      },
      { name: "PDF Files", extensions: ["pdf"] },
      { name: "Image Files", extensions: ["png", "jpg", "jpeg", "tif", "tiff"] },
      { name: "All Files", extensions: ["*"] },
    ],
    properties: ["openFile"],
  });

  if (result.canceled) return null;
  return result.filePaths[0];
});

ipcMain.handle("select-output-file", async (_event, defaultName) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: "Save Searchable PDF",
    defaultPath: defaultName || "output_ocr.pdf",
    filters: [{ name: "PDF Files", extensions: ["pdf"] }],
  });

  if (result.canceled) return null;
  return result.filePath;
});

ipcMain.handle("check-tesseract", async () => {
  return pythonBridge.send("check_tesseract", {});
});

ipcMain.handle("get-languages", async () => {
  return pythonBridge.send("get_languages", {});
});

ipcMain.handle("start-ocr", async (_event, params) => {
  // Stream progress events to renderer
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };

  return pythonBridge.send("start_ocr", params, onProgress);
});

ipcMain.handle("cancel-ocr", async () => {
  return pythonBridge.send("cancel_ocr", {});
});

ipcMain.handle("split-bilingual", async (_event, params) => {
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };

  return pythonBridge.send("split_bilingual", params, onProgress);
});

ipcMain.handle("open-file", async (_event, filePath) => {
  shell.openPath(filePath);
});

ipcMain.handle("show-in-folder", async (_event, filePath) => {
  shell.showItemInFolder(filePath);
});
