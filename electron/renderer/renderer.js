// ── DOM Elements ──

const inputPath = document.getElementById("input-path");
const outputPath = document.getElementById("output-path");
const btnBrowseInput = document.getElementById("btn-browse-input");
const btnBrowseOutput = document.getElementById("btn-browse-output");
const btnStart = document.getElementById("btn-start");
const btnCancel = document.getElementById("btn-cancel");
const btnClearLog = document.getElementById("btn-clear-log");
const progressSection = document.getElementById("progress-section");
const progressBar = document.getElementById("progress-bar");
const progressText = document.getElementById("progress-text");
const logOutput = document.getElementById("log-output");
const tesseractStatus = document.getElementById("tesseract-status");
const statusIcon = document.getElementById("status-icon");
const statusMessage = document.getElementById("status-message");

const modalOverlay = document.getElementById("modal-overlay");
const modalMessage = document.getElementById("modal-message");
const btnOpenFile = document.getElementById("btn-open-file");
const btnShowFolder = document.getElementById("btn-show-folder");
const btnModalClose = document.getElementById("btn-modal-close");

const langGrc = document.getElementById("lang-grc");
const langLat = document.getElementById("lang-lat");
const langEng = document.getElementById("lang-eng");
const dpiSelect = document.getElementById("dpi-select");

const splitEnabled = document.getElementById("split-enabled");
const splitSettings = document.getElementById("split-settings");
const splitPattern = document.getElementById("split-pattern");
const splitCustom = document.getElementById("split-custom");
const splitLangAPages = document.getElementById("split-lang-a-pages");
const splitLangBPages = document.getElementById("split-lang-b-pages");
const splitCommonPages = document.getElementById("split-common-pages");
const splitOutputA = document.getElementById("split-output-a");
const splitOutputB = document.getElementById("split-output-b");

const pagelabelsEnabled = document.getElementById("pagelabels-enabled");
const pagelabelsSettings = document.getElementById("pagelabels-settings");
const pagelabelsPreset = document.getElementById("pagelabels-preset");
const pagelabelsSimple = document.getElementById("pagelabels-simple");
const pagelabelsCustom = document.getElementById("pagelabels-custom");
const pagelabelsBodyStart = document.getElementById("pagelabels-body-start");
const pagelabelsRanges = document.getElementById("pagelabels-ranges");
const btnAddPagelabel = document.getElementById("btn-add-pagelabel");

const tocEnabled = document.getElementById("toc-enabled");
const tocSettings = document.getElementById("toc-settings");
const tocEntries = document.getElementById("toc-entries");
const btnAddToc = document.getElementById("btn-add-toc");
const btnImportToc = document.getElementById("btn-import-toc");
const tocImportArea = document.getElementById("toc-import-area");
const tocImportText = document.getElementById("toc-import-text");
const btnParseToc = document.getElementById("btn-parse-toc");

const autoDeskew = document.getElementById("auto-deskew");
const confidenceRetry = document.getElementById("confidence-retry");
const pageRangeInput = document.getElementById("page-range");
const zonePreset = document.getElementById("zone-preset");
const zoneHint = document.getElementById("zone-hint");
const zoneParams = document.getElementById("zone-params");
const zoneCustom = document.getElementById("zone-custom");
const zoneMarginWidth = document.getElementById("zone-margin-width");
const zoneMarginLabel = document.getElementById("zone-margin-label");
const zoneMarginTop = document.getElementById("zone-margin-top");
const zoneMarginTopLabel = document.getElementById("zone-margin-top-label");
const zoneMarginBottom = document.getElementById("zone-margin-bottom");
const zoneMarginBottomLabel = document.getElementById("zone-margin-bottom-label");
const zoneCustomEntries = document.getElementById("zone-custom-entries");
const zoneAutoDetect = document.getElementById("zone-auto-detect");
const btnDetectRegions = document.getElementById("btn-detect-regions");
const detectStatus = document.getElementById("detect-status");
const detectedRegionList = document.getElementById("detected-region-list");
const zoneBodyOnly = document.getElementById("zone-body-only");
const zoneBodyMargin = document.getElementById("zone-body-margin");
const zoneBodyMarginLabel = document.getElementById("zone-body-margin-label");
const btnAddZone = document.getElementById("btn-add-zone");

// Preprocessing elements
const preprocessEnabled = document.getElementById("preprocess-enabled");
const preprocessSettings = document.getElementById("preprocess-settings");
const ppDeskew = document.getElementById("pp-deskew");
const ppAutocontrast = document.getElementById("pp-autocontrast");
const ppDenoise = document.getElementById("pp-denoise");
const ppGrayscale = document.getElementById("pp-grayscale");
const ppBw = document.getElementById("pp-bw");
const ppBwSettings = document.getElementById("pp-bw-settings");
const ppBwThreshold = document.getElementById("pp-bw-threshold");
const ppBwLabel = document.getElementById("pp-bw-label");

// Preview elements
const previewPanel = document.getElementById("preview-panel");
const previewEmpty = document.getElementById("preview-empty");
const previewContent = document.getElementById("preview-content");
const previewImage = document.getElementById("preview-image");
const previewOverlay = document.getElementById("preview-overlay");
const previewPageInfo = document.getElementById("preview-page-info");
const btnPrevPage = document.getElementById("btn-prev-page");
const btnNextPage = document.getElementById("btn-next-page");
const pvShowZones = document.getElementById("pv-show-zones");
const pvShowPreprocess = document.getElementById("pv-show-preprocess");

// Zoom controls
const btnZoomIn = document.getElementById("btn-zoom-in");
const btnZoomOut = document.getElementById("btn-zoom-out");
const btnZoomFit = document.getElementById("btn-zoom-fit");
const zoomLabel = document.getElementById("zoom-label");

// Drop zone
const dropZone = document.getElementById("drop-zone");
const dropArea = document.getElementById("drop-area");

let currentOutputPath = "";
let removeProgressListener = null;

// Preview state
let previewPages = [];
let currentPage = 0;
let totalPages = 0;

// Detected text regions (per page): { pageIndex: [{x_start, y_start, x_end, y_end, ...}] }
let detectedRegions = {};
// Currently selected region index for resizing
let regionDragState = null;

// ── Logging ──

function log(message, type = "") {
  const line = document.createElement("div");
  line.className = `log-line ${type ? `log-${type}` : ""}`;
  line.textContent = message;
  logOutput.appendChild(line);
  logOutput.scrollTop = logOutput.scrollHeight;
}

// ── Helpers ──

function getBasePath(filePath) {
  const parts = filePath.split(/[\\/]/);
  const fileName = parts.pop();
  const dir = parts.join("/");
  const baseName = fileName.replace(/\.[^.]+$/, "");
  return { dir, baseName };
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Initialization ──

async function init() {
  tesseractStatus.classList.remove("hidden");
  statusIcon.textContent = "⟳";
  statusMessage.textContent = "Starting Python backend...";
  log("[INFO] Initializing (may install packages on first run)...", "info");

  try {
    const result = await window.api.checkTesseract();

    if (result.available) {
      tesseractStatus.className = "status-banner success";
      statusIcon.textContent = "✓";
      statusMessage.textContent = result.message;
      log(`[OK] ${result.message}`, "ok");

      const langResult = await window.api.getLanguages();
      const installed = langResult.installed || [];
      const langNames = { grc: "Ancient Greek", lat: "Latin", eng: "English" };

      for (const [code, checkbox] of Object.entries({ grc: langGrc, lat: langLat, eng: langEng })) {
        if (installed.includes(code)) {
          log(`  [OK] ${langNames[code]} (${code})`, "ok");
        } else {
          log(`  [WARN] ${langNames[code]} (${code}) not installed`, "warn");
          checkbox.checked = false;
          checkbox.disabled = true;
          checkbox.parentElement.style.opacity = "0.5";
        }
      }
    } else {
      tesseractStatus.className = "status-banner error";
      statusIcon.textContent = "✗";
      statusMessage.textContent = result.message;
      log(`[ERROR] ${result.message}`, "error");
    }
  } catch (err) {
    tesseractStatus.className = "status-banner error";
    statusIcon.textContent = "✗";
    const msg = err.message || "Unknown error";

    if (msg.includes("Missing Python packages")) {
      statusMessage.textContent = "Python packages not installed";
      log("[ERROR] " + msg, "error");
      log("[FIX] Run: ./scripts/run-dev.sh", "warn");
    } else if (msg.includes("Failed to start") || msg.includes("ENOENT")) {
      statusMessage.textContent = "Python not found";
      log("[ERROR] " + msg, "error");
      log("[FIX] Run: ./scripts/install-mac.sh", "warn");
    } else {
      statusMessage.textContent = "Python backend error";
      log("[ERROR] " + msg, "error");
    }
  }
}

// ── Drag & Drop ──

function handleFileInput(filePath) {
  inputPath.value = filePath;
  btnStart.disabled = false;

  const { dir, baseName } = getBasePath(filePath);
  outputPath.value = `${dir}/${baseName}_ocr.pdf`;
  splitOutputA.value = `${dir}/${baseName}_lang_a.pdf`;
  splitOutputB.value = `${dir}/${baseName}_lang_b.pdf`;

  log(`Input: ${filePath}`, "info");
  loadPreview(filePath);
}

// Drag & drop on the drop area
dropArea.addEventListener("click", () => btnBrowseInput.click());

document.addEventListener("dragover", (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropArea.classList.add("drag-over");
});

document.addEventListener("dragleave", (e) => {
  e.preventDefault();
  e.stopPropagation();
  if (!e.relatedTarget || !document.contains(e.relatedTarget)) {
    dropArea.classList.remove("drag-over");
  }
});

document.addEventListener("drop", (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropArea.classList.remove("drag-over");

  const files = Array.from(e.dataTransfer.files);
  if (files.length > 0) {
    const file = files[0];
    const ext = file.name.split(".").pop().toLowerCase();
    const supported = ["pdf", "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"];
    if (supported.includes(ext)) {
      handleFileInput(file.path);
    } else {
      log(`[WARN] Unsupported file type: .${ext}`, "warn");
    }
  }
});

// ── File Selection ──

btnBrowseInput.addEventListener("click", async () => {
  const filePath = await window.api.selectInputFile();
  if (filePath) handleFileInput(filePath);
});

btnBrowseOutput.addEventListener("click", async () => {
  const filePath = await window.api.selectOutputFile(outputPath.value);
  if (filePath) outputPath.value = filePath;
});

// ── Preview ──

async function loadPreview(filePath) {
  previewEmpty.classList.add("hidden");
  previewContent.classList.remove("hidden");
  previewPageInfo.textContent = "Loading...";

  try {
    const result = await window.api.loadPreview({ input: filePath, dpi: 72, max_width: 600 });
    previewPages = result.pages;
    totalPages = result.total;
    currentPage = 0;
    showPage(0);
    log(`[OK] Loaded ${totalPages} page(s) for preview`, "ok");
  } catch (err) {
    log(`[WARN] Preview failed: ${err.message}`, "warn");
    previewEmpty.classList.remove("hidden");
    previewContent.classList.add("hidden");
  }
}

function showPage(index) {
  if (index < 0 || index >= totalPages) return;
  currentPage = index;
  previewPageInfo.textContent = `${index + 1} / ${totalPages}`;

  if (pvShowPreprocess.checked && preprocessEnabled.checked) {
    loadPreprocessedPage(index);
  } else {
    const page = previewPages[index];
    previewImage.src = page.data;
    previewImage.onload = () => drawZoneOverlay();
  }
}

async function loadPreprocessedPage(index) {
  previewPageInfo.textContent = `${index + 1} / ${totalPages} (processing...)`;
  try {
    const result = await window.api.previewPreprocess({
      input: inputPath.value,
      page: index,
      dpi: 150,
      max_width: 600,
      deskew: ppDeskew.checked,
      grayscale: ppGrayscale.checked,
      bw: ppBw.checked,
      bw_threshold: parseInt(ppBwThreshold.value),
      denoise: ppDenoise.checked,
      autocontrast: ppAutocontrast.checked,
    });
    previewImage.src = result.data;
    previewImage.onload = () => drawZoneOverlay();
    previewPageInfo.textContent = `${index + 1} / ${totalPages}`;
  } catch (err) {
    log(`[WARN] Preprocess preview failed: ${err.message}`, "warn");
    // Fallback to original
    const page = previewPages[index];
    if (page) previewImage.src = page.data;
    previewPageInfo.textContent = `${index + 1} / ${totalPages}`;
  }
}

// ── Interactive Margin Drag State ──
let marginDragState = null; // { edge: "left"|"right", startX, startMargin }
const DRAG_HANDLE_WIDTH = 8; // px hit area for drag handles

function getMarginValues() {
  return {
    lr: parseInt(zoneMarginWidth.value) / 100,
    top: parseInt(zoneMarginTop.value) / 100,
    bottom: parseInt(zoneMarginBottom.value) / 100,
  };
}

function getMarginZones() {
  const preset = zonePreset.value;
  const m = getMarginValues();
  if (preset === "left_margin") {
    return [
      { x: 0, y: m.top, w: m.lr, h: 1 - m.top - m.bottom, label: "Margin" },
      { x: m.lr, y: m.top, w: 1 - m.lr, h: 1 - m.top - m.bottom, label: "Body" },
    ];
  } else if (preset === "both_margins") {
    const isEvenPage = (currentPage % 2 === 1);
    if (isEvenPage) {
      return [
        { x: 0, y: m.top, w: 1 - m.lr, h: 1 - m.top - m.bottom, label: "Body" },
        { x: 1 - m.lr, y: m.top, w: m.lr, h: 1 - m.top - m.bottom, label: "Margin" },
      ];
    }
    return [
      { x: 0, y: m.top, w: m.lr, h: 1 - m.top - m.bottom, label: "L.Margin" },
      { x: m.lr, y: m.top, w: 1 - 2 * m.lr, h: 1 - m.top - m.bottom, label: "Body" },
      { x: 1 - m.lr, y: m.top, w: m.lr, h: 1 - m.top - m.bottom, label: "R.Margin" },
    ];
  }
  return null;
}

function getDraggableEdges() {
  const preset = zonePreset.value;
  const m = getMarginValues();
  const edges = [];

  // Top/bottom edges (common to both presets)
  if (preset === "left_margin" || preset === "both_margins") {
    edges.push({ edge: "top", yFrac: m.top, axis: "h" });
    edges.push({ edge: "bottom", yFrac: 1 - m.bottom, axis: "h" });
  }

  if (preset === "left_margin") {
    edges.push({ edge: "right-of-left", xFrac: m.lr, axis: "v" });
  } else if (preset === "both_margins") {
    const isEvenPage = (currentPage % 2 === 1);
    if (isEvenPage) {
      edges.push({ edge: "left-of-right", xFrac: 1 - m.lr, axis: "v" });
    } else {
      edges.push({ edge: "right-of-left", xFrac: m.lr, axis: "v" });
      edges.push({ edge: "left-of-right", xFrac: 1 - m.lr, axis: "v" });
    }
  }
  return edges;
}

function drawZoneOverlay() {
  const cvs = previewOverlay;
  const img = previewImage;

  cvs.width = img.clientWidth;
  cvs.height = img.clientHeight;
  cvs.style.width = img.clientWidth + "px";
  cvs.style.height = img.clientHeight + "px";

  const wrapper = document.getElementById("preview-image-wrapper");
  const imgRect = img.getBoundingClientRect();
  const wrapperRect = wrapper.getBoundingClientRect();
  cvs.style.left = (imgRect.left - wrapperRect.left) + "px";
  cvs.style.top = (imgRect.top - wrapperRect.top) + "px";

  const ctx = cvs.getContext("2d");
  ctx.clearRect(0, 0, cvs.width, cvs.height);

  if (!pvShowZones.checked) return;

  const preset = zonePreset.value;
  if (preset === "full_page") return;

  const w = cvs.width;
  const h = cvs.height;
  const colors = ["rgba(52, 208, 88, 0.2)", "rgba(88, 166, 255, 0.2)", "rgba(248, 81, 73, 0.2)"];
  const borders = ["rgba(52, 208, 88, 0.6)", "rgba(88, 166, 255, 0.6)", "rgba(248, 81, 73, 0.6)"];

  let zones = [];
  if (preset === "left_margin" || preset === "both_margins") {
    zones = getMarginZones() || [];
    // Dim excluded top/bottom margins
    const m = getMarginValues();
    if (m.top > 0) {
      ctx.fillStyle = "rgba(248, 81, 73, 0.1)";
      ctx.fillRect(0, 0, w, m.top * h);
    }
    if (m.bottom > 0) {
      ctx.fillStyle = "rgba(248, 81, 73, 0.1)";
      ctx.fillRect(0, (1 - m.bottom) * h, w, m.bottom * h);
    }
  } else if (preset === "body_only") {
    const m = parseInt(zoneBodyMargin.value) / 100;
    zones = [
      { x: m, y: m, w: 1 - 2 * m, h: 1 - 2 * m, label: "Body" },
    ];
    // Dim the excluded margins
    ctx.fillStyle = "rgba(248, 81, 73, 0.15)";
    ctx.fillRect(0, 0, w, m * h);                     // top
    ctx.fillRect(0, (1 - m) * h, w, m * h);           // bottom
    ctx.fillRect(0, m * h, m * w, (1 - 2 * m) * h);   // left
    ctx.fillRect((1 - m) * w, m * h, m * w, (1 - 2 * m) * h); // right
  } else if (preset === "auto_detect") {
    const regions = detectedRegions[currentPage] || [];
    regions.forEach((r, i) => {
      const ci = i % colors.length;
      const rx = r.x_start * w;
      const ry = r.y_start * h;
      const rw = (r.x_end - r.x_start) * w;
      const rh = (r.y_end - r.y_start) * h;

      ctx.fillStyle = colors[ci];
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeStyle = borders[ci];
      ctx.lineWidth = 2;
      ctx.strokeRect(rx, ry, rw, rh);

      // Label
      ctx.fillStyle = borders[ci];
      ctx.font = "11px -apple-system, sans-serif";
      ctx.fillText(`R${i + 1}`, rx + 4, ry + 14);

      // Draw resize handles (small squares at corners and edges)
      const handleSize = 6;
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      // Corners
      for (const [hx, hy] of [[rx, ry], [rx + rw, ry], [rx, ry + rh], [rx + rw, ry + rh]]) {
        ctx.fillRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
        ctx.strokeStyle = borders[ci];
        ctx.lineWidth = 1;
        ctx.strokeRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
      }
    });
    return; // Skip margin-specific drawing below
  } else if (preset === "custom") {
    const rows = zoneCustomEntries.querySelectorAll(".zone-row");
    rows.forEach((row) => {
      zones.push({
        x: parseInt(row.querySelector(".zr-x1").value) / 100,
        y: parseInt(row.querySelector(".zr-y1").value) / 100,
        w: (parseInt(row.querySelector(".zr-x2").value) - parseInt(row.querySelector(".zr-x1").value)) / 100,
        h: (parseInt(row.querySelector(".zr-y2").value) - parseInt(row.querySelector(".zr-y1").value)) / 100,
        label: `PSM ${row.querySelector(".zr-psm").value}`,
      });
    });
  }

  zones.forEach((zone, i) => {
    const ci = i % colors.length;
    ctx.fillStyle = colors[ci];
    ctx.fillRect(zone.x * w, zone.y * h, zone.w * w, zone.h * h);
    ctx.strokeStyle = borders[ci];
    ctx.lineWidth = 2;
    ctx.strokeRect(zone.x * w, zone.y * h, zone.w * w, zone.h * h);
    ctx.fillStyle = borders[ci];
    ctx.font = "11px -apple-system, sans-serif";
    ctx.fillText(zone.label, zone.x * w + 4, zone.y * h + 14);
  });

  // Draw drag handles on all edges (for margin presets)
  const edges = getDraggableEdges();
  edges.forEach((e) => {
    ctx.fillStyle = "rgba(52, 208, 88, 0.7)";
    ctx.font = "bold 14px sans-serif";
    ctx.textAlign = "center";
    if (e.axis === "v") {
      // Vertical edge (left/right margin boundary)
      const xPx = e.xFrac * w;
      ctx.fillRect(xPx - 2, h * 0.35, 4, h * 0.3);
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillText("⇔", xPx, h * 0.5 + 5);
    } else {
      // Horizontal edge (top/bottom margin boundary)
      const yPx = e.yFrac * h;
      ctx.fillRect(w * 0.35, yPx - 2, w * 0.3, 4);
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillText("⇕", w * 0.5, yPx + 5);
    }
    ctx.textAlign = "left";
  });
}

// ── Margin Drag Interaction ──

previewOverlay.addEventListener("mousedown", (e) => {
  const preset = zonePreset.value;
  if (!pvShowZones.checked) return;

  const rect = previewOverlay.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;
  const w = previewOverlay.width;
  const h = previewOverlay.height;

  // Auto-detect: check region handles
  if (preset === "auto_detect") {
    const regions = detectedRegions[currentPage] || [];
    const HANDLE = 10;
    for (let i = 0; i < regions.length; i++) {
      const r = regions[i];
      const rx1 = r.x_start * w, ry1 = r.y_start * h;
      const rx2 = r.x_end * w, ry2 = r.y_end * h;

      // Check corners and edges for resize
      const handles = [
        { side: "nw", x: rx1, y: ry1 }, { side: "ne", x: rx2, y: ry1 },
        { side: "sw", x: rx1, y: ry2 }, { side: "se", x: rx2, y: ry2 },
        { side: "n", x: (rx1 + rx2) / 2, y: ry1 }, { side: "s", x: (rx1 + rx2) / 2, y: ry2 },
        { side: "w", x: rx1, y: (ry1 + ry2) / 2 }, { side: "e", x: rx2, y: (ry1 + ry2) / 2 },
      ];

      for (const handle of handles) {
        if (Math.abs(mouseX - handle.x) < HANDLE && Math.abs(mouseY - handle.y) < HANDLE) {
          regionDragState = { index: i, side: handle.side, origRegion: { ...r } };
          e.preventDefault();
          return;
        }
      }

      // Check if inside the box → move the whole region
      if (mouseX >= rx1 && mouseX <= rx2 && mouseY >= ry1 && mouseY <= ry2) {
        regionDragState = { index: i, side: "move", origRegion: { ...r }, startX: mouseX, startY: mouseY };
        previewOverlay.style.cursor = "move";
        e.preventDefault();
        return;
      }
    }
    return;
  }

  // Body only: drag margin edge
  if (preset === "body_only") {
    const m = parseInt(zoneBodyMargin.value) / 100;
    const edgesBody = [
      { edge: "left", pos: m * w }, { edge: "right", pos: (1 - m) * w },
      { edge: "top", pos: m * h }, { edge: "bottom", pos: (1 - m) * h },
    ];
    for (const eb of edgesBody) {
      const isHoriz = (eb.edge === "top" || eb.edge === "bottom");
      const dist = isHoriz ? Math.abs(mouseY - eb.pos) : Math.abs(mouseX - eb.pos);
      if (dist < DRAG_HANDLE_WIDTH) {
        marginDragState = { edge: "body-" + eb.edge, startMargin: parseInt(zoneBodyMargin.value) };
        previewOverlay.style.cursor = isHoriz ? "row-resize" : "col-resize";
        e.preventDefault();
        return;
      }
    }
    return;
  }

  // Margin presets (left_margin, both_margins)
  if (preset !== "left_margin" && preset !== "both_margins") return;

  const edges = getDraggableEdges();
  for (const edge of edges) {
    if (edge.axis === "v") {
      const edgePx = edge.xFrac * w;
      if (Math.abs(mouseX - edgePx) < DRAG_HANDLE_WIDTH) {
        marginDragState = { edge: edge.edge, axis: "v" };
        previewOverlay.style.cursor = "col-resize";
        e.preventDefault();
        return;
      }
    } else {
      const edgePx = edge.yFrac * h;
      if (Math.abs(mouseY - edgePx) < DRAG_HANDLE_WIDTH) {
        marginDragState = { edge: edge.edge, axis: "h" };
        previewOverlay.style.cursor = "row-resize";
        e.preventDefault();
        return;
      }
    }
  }
});

document.addEventListener("mousemove", (e) => {
  const rect = previewOverlay.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;
  const w = previewOverlay.width;
  const h = previewOverlay.height;

  // Handle region drag (auto_detect)
  if (regionDragState) {
    const regions = detectedRegions[currentPage] || [];
    const r = regions[regionDragState.index];
    if (!r) return;

    const orig = regionDragState.origRegion;
    const fracX = mouseX / w;
    const fracY = mouseY / h;
    const clamp = (v) => Math.max(0, Math.min(1, v));

    switch (regionDragState.side) {
      case "nw": r.x_start = clamp(fracX); r.y_start = clamp(fracY); break;
      case "ne": r.x_end = clamp(fracX); r.y_start = clamp(fracY); break;
      case "sw": r.x_start = clamp(fracX); r.y_end = clamp(fracY); break;
      case "se": r.x_end = clamp(fracX); r.y_end = clamp(fracY); break;
      case "n": r.y_start = clamp(fracY); break;
      case "s": r.y_end = clamp(fracY); break;
      case "w": r.x_start = clamp(fracX); break;
      case "e": r.x_end = clamp(fracX); break;
      case "move": {
        const dx = (mouseX - regionDragState.startX) / w;
        const dy = (mouseY - regionDragState.startY) / h;
        const rw = orig.x_end - orig.x_start;
        const rh = orig.y_end - orig.y_start;
        r.x_start = clamp(orig.x_start + dx);
        r.y_start = clamp(orig.y_start + dy);
        r.x_end = clamp(r.x_start + rw);
        r.y_end = clamp(r.y_start + rh);
        break;
      }
    }

    // Ensure min size
    if (r.x_end < r.x_start + 0.02) r.x_end = r.x_start + 0.02;
    if (r.y_end < r.y_start + 0.02) r.y_end = r.y_start + 0.02;

    drawZoneOverlay();
    renderRegionList(currentPage);
    return;
  }

  // Handle margin/body drag
  if (marginDragState) {
    if (marginDragState.edge.startsWith("body-")) {
      const side = marginDragState.edge.replace("body-", "");
      let newM;
      if (side === "left") newM = mouseX / w;
      else if (side === "right") newM = 1 - mouseX / w;
      else if (side === "top") newM = mouseY / h;
      else newM = 1 - mouseY / h;
      const pct = Math.round(Math.max(3, Math.min(25, newM * 100)));
      zoneBodyMargin.value = pct;
      zoneBodyMarginLabel.textContent = `${pct}%`;
      drawZoneOverlay();
      return;
    }

    if (marginDragState.edge === "top") {
      const pct = Math.round(Math.max(0, Math.min(30, (mouseY / h) * 100)));
      zoneMarginTop.value = pct;
      zoneMarginTopLabel.textContent = `${pct}%`;
    } else if (marginDragState.edge === "bottom") {
      const pct = Math.round(Math.max(0, Math.min(30, (1 - mouseY / h) * 100)));
      zoneMarginBottom.value = pct;
      zoneMarginBottomLabel.textContent = `${pct}%`;
    } else {
      let newMarginFrac;
      if (marginDragState.edge === "right-of-left") {
        newMarginFrac = mouseX / w;
      } else {
        newMarginFrac = 1 - (mouseX / w);
      }
      const newMarginPct = Math.round(Math.max(3, Math.min(40, newMarginFrac * 100)));
      zoneMarginWidth.value = newMarginPct;
      zoneMarginLabel.textContent = `${newMarginPct}%`;
    }
    drawZoneOverlay();
    return;
  }

  // Hover cursor updates
  const preset = zonePreset.value;
  if (!pvShowZones.checked) return;

  if (preset === "auto_detect") {
    const regions = detectedRegions[currentPage] || [];
    const HANDLE = 10;
    let cursor = "default";
    for (const r of regions) {
      const rx1 = r.x_start * w, ry1 = r.y_start * h;
      const rx2 = r.x_end * w, ry2 = r.y_end * h;
      // Check corners
      if (Math.abs(mouseX - rx1) < HANDLE && Math.abs(mouseY - ry1) < HANDLE) { cursor = "nw-resize"; break; }
      if (Math.abs(mouseX - rx2) < HANDLE && Math.abs(mouseY - ry1) < HANDLE) { cursor = "ne-resize"; break; }
      if (Math.abs(mouseX - rx1) < HANDLE && Math.abs(mouseY - ry2) < HANDLE) { cursor = "sw-resize"; break; }
      if (Math.abs(mouseX - rx2) < HANDLE && Math.abs(mouseY - ry2) < HANDLE) { cursor = "se-resize"; break; }
      // Edges
      if (mouseX >= rx1 && mouseX <= rx2 && Math.abs(mouseY - ry1) < HANDLE) { cursor = "n-resize"; break; }
      if (mouseX >= rx1 && mouseX <= rx2 && Math.abs(mouseY - ry2) < HANDLE) { cursor = "s-resize"; break; }
      if (mouseY >= ry1 && mouseY <= ry2 && Math.abs(mouseX - rx1) < HANDLE) { cursor = "w-resize"; break; }
      if (mouseY >= ry1 && mouseY <= ry2 && Math.abs(mouseX - rx2) < HANDLE) { cursor = "e-resize"; break; }
      // Inside
      if (mouseX >= rx1 && mouseX <= rx2 && mouseY >= ry1 && mouseY <= ry2) { cursor = "move"; break; }
    }
    previewOverlay.style.cursor = cursor;
  } else if (preset === "left_margin" || preset === "both_margins") {
    const edges = getDraggableEdges();
    let cursor = "default";
    for (const edge of edges) {
      if (edge.axis === "v" && Math.abs(mouseX - edge.xFrac * w) < DRAG_HANDLE_WIDTH) { cursor = "col-resize"; break; }
      if (edge.axis === "h" && Math.abs(mouseY - edge.yFrac * h) < DRAG_HANDLE_WIDTH) { cursor = "row-resize"; break; }
    }
    previewOverlay.style.cursor = cursor;
  } else {
    previewOverlay.style.cursor = "default";
  }
});

document.addEventListener("mouseup", () => {
  if (marginDragState) {
    marginDragState = null;
    previewOverlay.style.cursor = "default";
  }
  if (regionDragState) {
    regionDragState = null;
    previewOverlay.style.cursor = "default";
  }
});

btnPrevPage.addEventListener("click", () => showPage(currentPage - 1));
btnNextPage.addEventListener("click", () => showPage(currentPage + 1));

pvShowZones.addEventListener("change", drawZoneOverlay);
pvShowPreprocess.addEventListener("change", () => showPage(currentPage));

// Redraw zones when zone settings change
zonePreset.addEventListener("change", () => {
  const val = zonePreset.value;
  zoneHint.textContent = {
    full_page: "Standard single-pass OCR.",
    auto_detect: "Automatically detect text regions. Click 'Detect' then adjust boxes.",
    body_only: "Exclude margins — OCR only the central body text area.",
    left_margin: "Left margin + body. For Loeb, OCT, Teubner editions.",
    both_margins: "Left margin + body + right margin.",
    custom: "Define custom zones. PSM 11 for margins, PSM 3 for body.",
  }[val] || "";
  zoneParams.classList.toggle("hidden", val !== "left_margin" && val !== "both_margins");
  zoneCustom.classList.toggle("hidden", val !== "custom");
  zoneAutoDetect.classList.toggle("hidden", val !== "auto_detect");
  zoneBodyOnly.classList.toggle("hidden", val !== "body_only");
  drawZoneOverlay();
});

zoneMarginWidth.addEventListener("input", () => {
  zoneMarginLabel.textContent = `${zoneMarginWidth.value}%`;
  drawZoneOverlay();
});

zoneMarginTop.addEventListener("input", () => {
  zoneMarginTopLabel.textContent = `${zoneMarginTop.value}%`;
  drawZoneOverlay();
});

zoneMarginBottom.addEventListener("input", () => {
  zoneMarginBottomLabel.textContent = `${zoneMarginBottom.value}%`;
  drawZoneOverlay();
});

zoneBodyMargin.addEventListener("input", () => {
  zoneBodyMarginLabel.textContent = `${zoneBodyMargin.value}%`;
  drawZoneOverlay();
});

// ── Auto Detect Regions ──

btnDetectRegions.addEventListener("click", async () => {
  if (!inputPath.value) { log("[WARN] No file loaded", "warn"); return; }
  btnDetectRegions.disabled = true;
  btnDetectRegions.textContent = "Detecting...";
  detectStatus.textContent = "";

  try {
    const lang = getSelectedLanguages();
    const result = await window.api.detectRegions({
      input: inputPath.value,
      page: currentPage,
      dpi: 150,
      lang,
    });

    detectedRegions[currentPage] = result.regions;
    detectStatus.textContent = `Found ${result.total} text region(s). Drag edges to adjust.`;
    renderRegionList(currentPage);
    drawZoneOverlay();
    log(`[OK] Detected ${result.total} text regions on page ${currentPage + 1}`, "ok");
  } catch (err) {
    log(`[ERROR] Region detection failed: ${err.message}`, "error");
    detectStatus.textContent = "Detection failed.";
  } finally {
    btnDetectRegions.disabled = false;
    btnDetectRegions.textContent = "Detect Text Regions";
  }
});

function renderRegionList(pageIndex) {
  detectedRegionList.innerHTML = "";
  const regions = detectedRegions[pageIndex] || [];
  regions.forEach((r, i) => {
    const row = document.createElement("div");
    row.className = "zone-row";
    row.style.fontSize = "11px";
    const pct = (v) => Math.round(v * 100);
    row.innerHTML = `
      <span style="color:var(--green);min-width:18px;">R${i + 1}</span>
      <span style="color:var(--text-muted);">${pct(r.x_start)}%-${pct(r.x_end)}% × ${pct(r.y_start)}%-${pct(r.y_end)}%</span>
      <span style="color:var(--text-muted);margin-left:auto;">${r.word_count}w</span>
      <button class="zone-delete" data-idx="${i}">&times;</button>
    `;
    row.querySelector(".zone-delete").addEventListener("click", () => {
      regions.splice(i, 1);
      renderRegionList(pageIndex);
      drawZoneOverlay();
    });
    detectedRegionList.appendChild(row);
  });
}

// ── Toggle Sections ──

preprocessEnabled.addEventListener("change", () => {
  preprocessSettings.classList.toggle("hidden", !preprocessEnabled.checked);
});

ppBw.addEventListener("change", () => {
  ppBwSettings.classList.toggle("hidden", !ppBw.checked);
  if (ppBw.checked) ppGrayscale.checked = false;
});

ppGrayscale.addEventListener("change", () => {
  if (ppGrayscale.checked) ppBw.checked = false;
  ppBwSettings.classList.add("hidden");
});

ppBwThreshold.addEventListener("input", () => {
  ppBwLabel.textContent = ppBwThreshold.value;
});

// Refresh preview on preprocess toggle changes
[ppDeskew, ppAutocontrast, ppDenoise, ppGrayscale, ppBw].forEach((el) => {
  el.addEventListener("change", () => {
    if (pvShowPreprocess.checked && preprocessEnabled.checked && totalPages > 0) {
      showPage(currentPage);
    }
  });
});
ppBwThreshold.addEventListener("change", () => {
  if (pvShowPreprocess.checked && ppBw.checked && totalPages > 0) {
    showPage(currentPage);
  }
});

splitEnabled.addEventListener("change", () => splitSettings.classList.toggle("hidden", !splitEnabled.checked));
splitPattern.addEventListener("change", () => splitCustom.classList.toggle("hidden", splitPattern.value !== "custom"));
pagelabelsEnabled.addEventListener("change", () => pagelabelsSettings.classList.toggle("hidden", !pagelabelsEnabled.checked));
pagelabelsPreset.addEventListener("change", () => {
  const isCustom = pagelabelsPreset.value === "custom";
  pagelabelsSimple.classList.toggle("hidden", isCustom);
  pagelabelsCustom.classList.toggle("hidden", !isCustom);
});
tocEnabled.addEventListener("change", () => tocSettings.classList.toggle("hidden", !tocEnabled.checked));

// ── Zone Custom Rows ──

function addCustomZoneRow(xStart = 0, yStart = 0, xEnd = 100, yEnd = 100, psm = 3) {
  const row = document.createElement("div");
  row.className = "zone-row";
  row.innerHTML = `
    <span style="color:var(--text-secondary)">x:</span>
    <input type="number" class="text-input zr-x1" value="${xStart}" min="0" max="100">
    <span>-</span>
    <input type="number" class="text-input zr-x2" value="${xEnd}" min="0" max="100">
    <span style="color:var(--text-secondary)">y:</span>
    <input type="number" class="text-input zr-y1" value="${yStart}" min="0" max="100">
    <span>-</span>
    <input type="number" class="text-input zr-y2" value="${yEnd}" min="0" max="100">
    <select class="select-input zr-psm">
      <option value="3" ${psm === 3 ? "selected" : ""}>PSM 3</option>
      <option value="11" ${psm === 11 ? "selected" : ""}>PSM 11</option>
      <option value="6" ${psm === 6 ? "selected" : ""}>PSM 6</option>
      <option value="4" ${psm === 4 ? "selected" : ""}>PSM 4</option>
    </select>
    <button class="zone-delete">&times;</button>
  `;
  row.querySelector(".zone-delete").addEventListener("click", () => { row.remove(); drawZoneOverlay(); });
  // Redraw on change
  row.querySelectorAll("input, select").forEach((el) => el.addEventListener("change", drawZoneOverlay));
  zoneCustomEntries.appendChild(row);
  drawZoneOverlay();
}

btnAddZone.addEventListener("click", () => addCustomZoneRow());

// ── Language / Config Getters ──

function getSelectedLanguages() {
  const langs = [];
  if (langGrc.checked) langs.push("grc");
  if (langLat.checked) langs.push("lat");
  if (langEng.checked) langs.push("eng");
  return langs.length > 0 ? langs.join("+") : "eng";
}

function getZoneConfig() {
  const preset = zonePreset.value;
  if (preset === "full_page") return {};
  if (preset === "auto_detect") {
    // Collect all detected regions across pages as custom zones
    const allRegions = [];
    for (const pageIdx in detectedRegions) {
      for (const r of detectedRegions[pageIdx]) {
        allRegions.push({
          type: "body",
          x_start: r.x_start,
          y_start: r.y_start,
          x_end: r.x_end,
          y_end: r.y_end,
          psm: 3,
        });
      }
    }
    if (allRegions.length === 0) return {}; // fallback to full page
    return { zone_preset: "custom", zones: allRegions };
  }
  if (preset === "body_only") {
    const m = parseInt(zoneBodyMargin.value) / 100;
    return {
      zone_preset: "custom",
      zones: [{ type: "body", x_start: m, y_start: m, x_end: 1 - m, y_end: 1 - m, psm: 3 }],
    };
  }
  if (preset === "custom") {
    const rows = zoneCustomEntries.querySelectorAll(".zone-row");
    const zones = [];
    rows.forEach((row) => {
      zones.push({
        type: "body",
        x_start: parseInt(row.querySelector(".zr-x1").value) / 100,
        y_start: parseInt(row.querySelector(".zr-y1").value) / 100,
        x_end: parseInt(row.querySelector(".zr-x2").value) / 100,
        y_end: parseInt(row.querySelector(".zr-y2").value) / 100,
        psm: parseInt(row.querySelector(".zr-psm").value),
      });
    });
    return { zone_preset: "custom", zones };
  }
  const m = getMarginValues();
  const zoneParamsObj = { body_margin_top: m.top, body_margin_bottom: m.bottom };
  if (preset === "left_margin") zoneParamsObj.margin_width = m.lr;
  else if (preset === "both_margins") { zoneParamsObj.left_margin = m.lr; zoneParamsObj.right_margin = m.lr; }
  return { zone_preset: preset, zone_params: zoneParamsObj };
}

function getPreprocessConfig() {
  if (!preprocessEnabled.checked) return null;
  return {
    deskew: ppDeskew.checked,
    grayscale: ppGrayscale.checked,
    bw: ppBw.checked,
    bw_threshold: parseInt(ppBwThreshold.value),
    denoise: ppDenoise.checked,
    autocontrast: ppAutocontrast.checked,
  };
}

function getPageLabels() {
  if (!pagelabelsEnabled.checked) return null;
  if (pagelabelsPreset.value === "roman-arabic") {
    const bodyStart = parseInt(pagelabelsBodyStart.value) || 1;
    const ranges = [{ start_page: 0, style: "roman_lower", start_number: 1 }];
    if (bodyStart > 1) ranges.push({ start_page: bodyStart - 1, style: "arabic", start_number: 1 });
    return ranges;
  }
  const rows = pagelabelsRanges.querySelectorAll(".pagelabel-row");
  const ranges = [];
  rows.forEach((row) => {
    ranges.push({ start_page: (parseInt(row.querySelector(".pl-start").value) || 1) - 1, style: row.querySelector(".pl-style").value, start_number: parseInt(row.querySelector(".pl-startnum").value) || 1 });
  });
  return ranges.length > 0 ? ranges : null;
}

function addPageLabelRow(startPage = 1, style = "arabic", startNum = 1) {
  const row = document.createElement("div");
  row.className = "pagelabel-row";
  row.innerHTML = `
    <span style="color:var(--text-secondary);font-size:11px;">Page</span>
    <input type="number" class="text-input pl-start" value="${startPage}" min="1" style="width:50px;">
    <select class="select-input pl-style">
      <option value="roman_lower" ${style === "roman_lower" ? "selected" : ""}>i,ii,iii</option>
      <option value="roman_upper" ${style === "roman_upper" ? "selected" : ""}>I,II,III</option>
      <option value="arabic" ${style === "arabic" ? "selected" : ""}>1,2,3</option>
    </select>
    <span style="color:var(--text-secondary);font-size:11px;">from</span>
    <input type="number" class="text-input pl-startnum" value="${startNum}" min="1" style="width:45px;">
    <button class="pagelabel-delete">&times;</button>
  `;
  row.querySelector(".pagelabel-delete").addEventListener("click", () => row.remove());
  pagelabelsRanges.appendChild(row);
}
btnAddPagelabel.addEventListener("click", () => addPageLabelRow());

// ── TOC Editor ──

function getTocEntries() {
  if (!tocEnabled.checked) return null;
  const rows = tocEntries.querySelectorAll(".toc-entry-row");
  const entries = [];
  rows.forEach((row) => {
    const title = row.querySelector(".toc-title").value.trim();
    const page = parseInt(row.querySelector(".toc-page").value) || 1;
    const level = parseInt(row.dataset.level) || 0;
    if (title) entries.push({ title, page: page - 1, level });
  });
  return entries.length > 0 ? entries : null;
}

function addTocEntry(title = "", page = 1, level = 0) {
  const row = document.createElement("div");
  row.className = "toc-entry-row";
  row.dataset.level = level;
  row.style.paddingLeft = `${level * 16}px`;
  row.innerHTML = `
    <button class="toc-indent-btn toc-outdent" title="Outdent">&lt;</button>
    <button class="toc-indent-btn toc-indent" title="Indent">&gt;</button>
    <span class="toc-level-indicator">L${level}</span>
    <input type="text" class="text-input toc-title" placeholder="Title" value="${escapeHtml(title)}">
    <input type="number" class="text-input toc-page" placeholder="Pg" value="${page}" min="1" style="width:50px;">
    <button class="toc-delete">&times;</button>
  `;
  const updateLevel = (n) => { const c = Math.max(0, Math.min(3, n)); row.dataset.level = c; row.style.paddingLeft = `${c * 16}px`; row.querySelector(".toc-level-indicator").textContent = `L${c}`; };
  row.querySelector(".toc-outdent").addEventListener("click", () => updateLevel(parseInt(row.dataset.level) - 1));
  row.querySelector(".toc-indent").addEventListener("click", () => updateLevel(parseInt(row.dataset.level) + 1));
  row.querySelector(".toc-delete").addEventListener("click", () => row.remove());
  tocEntries.appendChild(row);
}

btnAddToc.addEventListener("click", () => addTocEntry());
btnImportToc.addEventListener("click", () => tocImportArea.classList.toggle("hidden"));

btnParseToc.addEventListener("click", () => {
  const text = tocImportText.value;
  if (!text.trim()) return;
  const lines = text.split("\n");
  for (const line of lines) {
    if (!line.trim()) continue;
    const stripped = line.replace(/^\s+/, "");
    const indent = line.length - stripped.length;
    const level = Math.min(3, Math.floor(indent / 2));
    const match = stripped.match(/^(.+?)[\s.…·\-_]+(\d+)\s*$/) || stripped.match(/^(.+?)\t+(\d+)\s*$/);
    if (match) addTocEntry(match[1].trim(), parseInt(match[2]), level);
    else addTocEntry(stripped.trim(), 1, level);
  }
  tocImportArea.classList.add("hidden");
  tocImportText.value = "";
  log(`[OK] Imported ${lines.filter((l) => l.trim()).length} TOC entries`, "ok");
});

// ── OCR Processing ──

function setupProgressListener() {
  removeProgressListener = window.api.onOcrProgress((data) => {
    if (data.current != null && data.total > 0) {
      progressBar.style.width = `${Math.round((data.current / data.total) * 100)}%`;
    }
    if (data.message) { progressText.textContent = data.message; log(data.message); }
    if (data.page_result) {
      const r = data.page_result;
      log(`  Page ${r.page}: ${r.words} words, confidence: ${r.confidence.toFixed(1)}%`, "ok");
    }
  });
}

function cleanupProgress() {
  btnStart.disabled = false;
  btnCancel.disabled = true;
  if (removeProgressListener) { removeProgressListener(); removeProgressListener = null; }
}

btnStart.addEventListener("click", async () => {
  const input = inputPath.value;
  if (!input) return;

  let output = outputPath.value;
  if (!output) { const { dir, baseName } = getBasePath(input); output = `${dir}/${baseName}_ocr.pdf`; outputPath.value = output; }

  const lang = getSelectedLanguages();
  const dpi = parseInt(dpiSelect.value);
  const isSplit = splitEnabled.checked;

  log("", "");
  log(`Starting OCR: lang=${lang}, dpi=${dpi}${isSplit ? " [split]" : ""}`, "info");

  btnStart.disabled = true;
  btnCancel.disabled = false;
  progressSection.classList.remove("hidden");
  progressBar.style.width = "0%";
  progressText.textContent = "Loading...";
  setupProgressListener();

  try {
    if (isSplit) {
      const langAPages = splitPattern.value === "custom" ? splitLangAPages.value || "odd" : "odd";
      const langBPages = splitPattern.value === "custom" ? splitLangBPages.value || "even" : "even";
      const outputA = splitOutputA.value || `${getBasePath(input).dir}/${getBasePath(input).baseName}_lang_a.pdf`;
      const outputB = splitOutputB.value || `${getBasePath(input).dir}/${getBasePath(input).baseName}_lang_b.pdf`;

      const result = await window.api.splitBilingual({
        input, output_a: outputA, output_b: outputB, lang, dpi,
        lang_a_pages: langAPages, lang_b_pages: langBPages, common_pages: splitCommonPages.value || "",
      });

      progressBar.style.width = "100%";
      progressText.textContent = "Complete!";
      log(`[DONE] A: ${result.output_a} (${result.pages_a} pages)`, "ok");
      log(`[DONE] B: ${result.output_b} (${result.pages_b} pages)`, "ok");
      currentOutputPath = result.output_a;
      modalMessage.textContent = `A: ${result.output_a}\nB: ${result.output_b}`;
      modalOverlay.classList.remove("hidden");
    } else {
      const params = { input, output, lang, dpi };
      if (autoDeskew.checked) params.auto_deskew = true;
      if (confidenceRetry.checked) params.min_confidence = 95.0;
      if (pageRangeInput.value.trim()) params.page_range = pageRangeInput.value.trim();
      Object.assign(params, getZoneConfig());
      const preprocess = getPreprocessConfig();
      if (preprocess) params.preprocess = preprocess;
      const pageLabels = getPageLabels();
      if (pageLabels) params.page_labels = pageLabels;
      const toc = getTocEntries();
      if (toc) params.toc = toc;

      const result = await window.api.startOcr(params);
      progressBar.style.width = "100%";
      progressText.textContent = "Complete!";
      log(`[DONE] ${result.output_path}`, "ok");
      currentOutputPath = result.output_path;
      modalMessage.textContent = result.output_path;
      modalOverlay.classList.remove("hidden");
    }
  } catch (err) {
    log(`[ERROR] ${err.message}`, "error");
    progressText.textContent = "Error";
  } finally {
    cleanupProgress();
  }
});

btnCancel.addEventListener("click", async () => {
  try { await window.api.cancelOcr(); log("[CANCELLED]", "warn"); } catch (err) { log(`[ERROR] ${err.message}`, "error"); }
  cleanupProgress();
  progressText.textContent = "Cancelled";
});

// ── Modal ──

btnOpenFile.addEventListener("click", () => { window.api.openFile(currentOutputPath); modalOverlay.classList.add("hidden"); });
btnShowFolder.addEventListener("click", () => { window.api.showInFolder(currentOutputPath); modalOverlay.classList.add("hidden"); });
btnModalClose.addEventListener("click", () => modalOverlay.classList.add("hidden"));
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) modalOverlay.classList.add("hidden"); });

// ── Clear Log ──

btnClearLog.addEventListener("click", () => { logOutput.innerHTML = ""; });

// ── Auto-Updater ──

const updateBanner = document.getElementById("update-banner");
const updateMessage = document.getElementById("update-message");
const updateProgressBar = document.getElementById("update-progress-bar");
const updateProgressFill = document.getElementById("update-progress-fill");
const btnUpdateDownload = document.getElementById("btn-update-download");
const btnUpdateInstall = document.getElementById("btn-update-install");
const btnUpdateDismiss = document.getElementById("btn-update-dismiss");

window.api.onUpdaterStatus((data) => {
  switch (data.status) {
    case "available":
      updateBanner.classList.remove("hidden", "update-ready");
      updateMessage.textContent = `Update: v${data.version}`;
      btnUpdateDownload.classList.remove("hidden");
      btnUpdateInstall.classList.add("hidden");
      updateProgressBar.classList.add("hidden");
      break;
    case "downloading":
      updateMessage.textContent = `Downloading ${Math.round(data.percent)}%`;
      updateProgressBar.classList.remove("hidden");
      updateProgressFill.style.width = `${data.percent}%`;
      btnUpdateDownload.classList.add("hidden");
      break;
    case "ready":
      updateBanner.classList.add("update-ready");
      updateMessage.textContent = `v${data.version} ready`;
      updateProgressBar.classList.add("hidden");
      btnUpdateDownload.classList.add("hidden");
      btnUpdateInstall.classList.remove("hidden");
      break;
    case "up-to-date":
      log(`[OK] ${data.message}`, "ok");
      break;
    case "error":
      log(`[UPDATE] ${data.message}`, "warn");
      break;
  }
});

btnUpdateDownload.addEventListener("click", async () => { btnUpdateDownload.disabled = true; btnUpdateDownload.textContent = "..."; await window.api.updaterDownload(); });
btnUpdateInstall.addEventListener("click", async () => { await window.api.updaterInstall(); });
btnUpdateDismiss.addEventListener("click", () => { updateBanner.classList.add("hidden"); });

// ── Zoom ──

let zoomLevel = 1.0;

function applyZoom() {
  previewImage.style.maxWidth = zoomLevel === 1.0 ? "100%" : "none";
  previewImage.style.maxHeight = zoomLevel === 1.0 ? "100%" : "none";
  previewImage.style.width = zoomLevel === 1.0 ? "" : `${zoomLevel * 100}%`;
  zoomLabel.textContent = `${Math.round(zoomLevel * 100)}%`;
  // Redraw overlay at new zoom size
  setTimeout(drawZoneOverlay, 50);
}

btnZoomIn.addEventListener("click", () => {
  zoomLevel = Math.min(5.0, zoomLevel + 0.25);
  applyZoom();
});

btnZoomOut.addEventListener("click", () => {
  zoomLevel = Math.max(0.25, zoomLevel - 0.25);
  applyZoom();
});

btnZoomFit.addEventListener("click", () => {
  zoomLevel = 1.0;
  applyZoom();
});

// Mouse wheel zoom on preview
previewOverlay.addEventListener("wheel", (e) => {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    zoomLevel = Math.max(0.25, Math.min(5.0, zoomLevel + delta));
    applyZoom();
  }
}, { passive: false });

// ── Window resize → redraw overlay ──

window.addEventListener("resize", drawZoneOverlay);

// ── Start ──

init();
