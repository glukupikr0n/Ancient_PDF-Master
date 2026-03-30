const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const path = require("path");
const { PythonBridge } = require("./python-bridge");
const { initAutoUpdater } = require("./auto-updater");

let mainWindow;
let pythonBridge;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: "#111111",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
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
  initAutoUpdater(mainWindow);

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

ipcMain.handle("load-preview", async (_event, params) => {
  return pythonBridge.send("load_preview", params);
});

ipcMain.handle("preview-preprocess", async (_event, params) => {
  return pythonBridge.send("preview_preprocess", params);
});

ipcMain.handle("detect-regions", async (_event, params) => {
  return pythonBridge.send("detect_regions", params);
});

ipcMain.handle("detect-toc", async (_event, params) => {
  return pythonBridge.send("detect_toc", params);
});

// ── Training IPC Handlers ──

ipcMain.handle("check-training-tools", async () => {
  return pythonBridge.send("check_training_tools", {});
});

ipcMain.handle("list-custom-models", async () => {
  return pythonBridge.send("list_custom_models", {});
});

ipcMain.handle("delete-custom-model", async (_event, params) => {
  return pythonBridge.send("delete_custom_model", params);
});

ipcMain.handle("validate-training-data", async (_event, params) => {
  return pythonBridge.send("validate_training_data", params);
});

ipcMain.handle("generate-line-images", async (_event, params) => {
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };
  return pythonBridge.send("generate_line_images", params, onProgress);
});

ipcMain.handle("start-training", async (_event, params) => {
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };
  return pythonBridge.send("start_training", params, onProgress);
});

ipcMain.handle("select-training-dir", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Training Data Directory",
    properties: ["openDirectory"],
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

// ── Dataset IPC Handlers ──

ipcMain.handle("list-available-datasets", async () => {
  return pythonBridge.send("list_available_datasets", {});
});

ipcMain.handle("list-downloaded-datasets", async () => {
  return pythonBridge.send("list_downloaded_datasets", {});
});

ipcMain.handle("download-dataset", async (_event, params) => {
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };
  return pythonBridge.send("download_dataset", params, onProgress);
});

ipcMain.handle("convert-dataset", async (_event, params) => {
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };
  return pythonBridge.send("convert_dataset", params, onProgress);
});

ipcMain.handle("delete-dataset", async (_event, params) => {
  return pythonBridge.send("delete_dataset", params);
});

ipcMain.handle("select-dataset-output-dir", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "Select Output Directory for Training Data",
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

ipcMain.handle("start-upscale", async (_event, params) => {
  const onProgress = (data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("ocr-progress", data);
    }
  };
  return pythonBridge.send("upscale", params, onProgress);
});

ipcMain.handle("select-upscale-output", async (_event, defaultName) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: "Save Upscaled File",
    defaultPath: defaultName || "upscaled.pdf",
    filters: [
      { name: "PDF Files", extensions: ["pdf"] },
      { name: "PNG Images", extensions: ["png"] },
      { name: "JPEG Images", extensions: ["jpg"] },
      { name: "TIFF Images", extensions: ["tiff"] },
    ],
  });
  if (result.canceled) return null;
  return result.filePath;
});

ipcMain.handle("get-setup-status", async () => {
  if (!pythonBridge) return { message: "Initializing..." };
  return { message: pythonBridge._setupMessage || null };
});

ipcMain.handle("open-file", async (_event, filePath) => {
  shell.openPath(filePath);
});

ipcMain.handle("show-in-folder", async (_event, filePath) => {
  shell.showItemInFolder(filePath);
});
