const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  // File dialogs
  selectInputFile: () => ipcRenderer.invoke("select-input-file"),
  selectOutputFile: (defaultName) =>
    ipcRenderer.invoke("select-output-file", defaultName),

  // Tesseract
  checkTesseract: () => ipcRenderer.invoke("check-tesseract"),
  getLanguages: () => ipcRenderer.invoke("get-languages"),

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

  // File operations
  openFile: (path) => ipcRenderer.invoke("open-file", path),
  showInFolder: (path) => ipcRenderer.invoke("show-in-folder", path),
});
