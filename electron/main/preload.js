const { contextBridge, ipcRenderer, webUtils } = require("electron");

contextBridge.exposeInMainWorld("api", {
  // File dialogs
  selectInputFile: () => ipcRenderer.invoke("select-input-file"),
  selectOutputFile: (defaultName) =>
    ipcRenderer.invoke("select-output-file", defaultName),

  // Get file path from dropped File object (Electron 33+)
  getPathForFile: (file) => webUtils.getPathForFile(file),

  // Setup
  getSetupStatus: () => ipcRenderer.invoke("get-setup-status"),

  // Tesseract
  checkTesseract: () => ipcRenderer.invoke("check-tesseract"),
  getLanguages: () => ipcRenderer.invoke("get-languages"),

  // Training
  checkTrainingTools: () => ipcRenderer.invoke("check-training-tools"),
  listCustomModels: () => ipcRenderer.invoke("list-custom-models"),
  deleteCustomModel: (params) => ipcRenderer.invoke("delete-custom-model", params),
  validateTrainingData: (params) => ipcRenderer.invoke("validate-training-data", params),
  generateLineImages: (params) => ipcRenderer.invoke("generate-line-images", params),
  startTraining: (params) => ipcRenderer.invoke("start-training", params),
  selectTrainingDir: () => ipcRenderer.invoke("select-training-dir"),

  // OCR
  startOcr: (params) => ipcRenderer.invoke("start-ocr", params),
  cancelOcr: () => ipcRenderer.invoke("cancel-ocr"),
  splitBilingual: (params) => ipcRenderer.invoke("split-bilingual", params),

  // Progress listener
  onOcrProgress: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("ocr-progress", handler);
    return () => ipcRenderer.removeListener("ocr-progress", handler);
  },

  // Preview
  loadPreview: (params) => ipcRenderer.invoke("load-preview", params),
  previewPreprocess: (params) => ipcRenderer.invoke("preview-preprocess", params),
  detectRegions: (params) => ipcRenderer.invoke("detect-regions", params),
  detectToc: (params) => ipcRenderer.invoke("detect-toc", params),

  // File operations
  openFile: (path) => ipcRenderer.invoke("open-file", path),
  showInFolder: (path) => ipcRenderer.invoke("show-in-folder", path),

  // Upscale
  startUpscale: (params) => ipcRenderer.invoke("start-upscale", params),
  selectUpscaleOutput: (defaultName) => ipcRenderer.invoke("select-upscale-output", defaultName),

  // Auto-updater
  updaterCheck: () => ipcRenderer.invoke("updater-check"),
  updaterDownload: () => ipcRenderer.invoke("updater-download"),
  updaterInstall: () => ipcRenderer.invoke("updater-install"),
  updaterGetVersion: () => ipcRenderer.invoke("updater-get-version"),
  onUpdaterStatus: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("updater-status", handler);
    return () => ipcRenderer.removeListener("updater-status", handler);
  },
});
