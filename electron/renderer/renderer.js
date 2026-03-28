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

// Modal elements
const modalOverlay = document.getElementById("modal-overlay");
const modalMessage = document.getElementById("modal-message");
const btnOpenFile = document.getElementById("btn-open-file");
const btnShowFolder = document.getElementById("btn-show-folder");
const btnModalClose = document.getElementById("btn-modal-close");

// Language checkboxes
const langGrc = document.getElementById("lang-grc");
const langLat = document.getElementById("lang-lat");
const langEng = document.getElementById("lang-eng");
const dpiSelect = document.getElementById("dpi-select");

// Split elements
const splitEnabled = document.getElementById("split-enabled");
const splitSettings = document.getElementById("split-settings");
const splitPattern = document.getElementById("split-pattern");
const splitCustom = document.getElementById("split-custom");
const splitLangAPages = document.getElementById("split-lang-a-pages");
const splitLangBPages = document.getElementById("split-lang-b-pages");
const splitCommonPages = document.getElementById("split-common-pages");
const splitOutputA = document.getElementById("split-output-a");
const splitOutputB = document.getElementById("split-output-b");

// Page labels elements
const pagelabelsEnabled = document.getElementById("pagelabels-enabled");
const pagelabelsSettings = document.getElementById("pagelabels-settings");
const pagelabelsPreset = document.getElementById("pagelabels-preset");
const pagelabelsSimple = document.getElementById("pagelabels-simple");
const pagelabelsCustom = document.getElementById("pagelabels-custom");
const pagelabelsBodyStart = document.getElementById("pagelabels-body-start");
const pagelabelsRanges = document.getElementById("pagelabels-ranges");
const btnAddPagelabel = document.getElementById("btn-add-pagelabel");

// TOC elements
const tocEnabled = document.getElementById("toc-enabled");
const tocSettings = document.getElementById("toc-settings");
const tocEntries = document.getElementById("toc-entries");
const btnAddToc = document.getElementById("btn-add-toc");
const btnImportToc = document.getElementById("btn-import-toc");
const tocImportArea = document.getElementById("toc-import-area");
const tocImportText = document.getElementById("toc-import-text");
const btnParseToc = document.getElementById("btn-parse-toc");

let currentOutputPath = "";
let removeProgressListener = null;

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

// ── Initialization ──

async function init() {
  try {
    const result = await window.api.checkTesseract();
    tesseractStatus.classList.remove("hidden");

    if (result.available) {
      tesseractStatus.classList.add("success");
      statusIcon.textContent = "✓";
      statusMessage.textContent = result.message;
      log(`[OK] ${result.message}`, "ok");

      // Check installed language packs
      const langResult = await window.api.getLanguages();
      const installed = langResult.installed || [];
      const langNames = { grc: "Ancient Greek", lat: "Latin", eng: "English" };

      for (const [code, checkbox] of Object.entries({
        grc: langGrc,
        lat: langLat,
        eng: langEng,
      })) {
        if (installed.includes(code)) {
          log(`  [OK] ${langNames[code]} (${code}) installed`, "ok");
        } else {
          log(`  [WARN] ${langNames[code]} (${code}) not installed`, "warn");
          checkbox.checked = false;
          checkbox.disabled = true;
          checkbox.parentElement.style.opacity = "0.5";
        }
      }
    } else {
      tesseractStatus.classList.add("error");
      statusIcon.textContent = "✗";
      statusMessage.textContent = result.message;
      log(`[ERROR] ${result.message}`, "error");
    }
  } catch (err) {
    tesseractStatus.classList.remove("hidden");
    tesseractStatus.classList.add("error");
    statusIcon.textContent = "✗";
    statusMessage.textContent = "Failed to connect to Python backend";
    log("[ERROR] Failed to connect to Python backend: " + err.message, "error");
  }
}

// ── File Selection ──

btnBrowseInput.addEventListener("click", async () => {
  const filePath = await window.api.selectInputFile();
  if (filePath) {
    inputPath.value = filePath;
    btnStart.disabled = false;

    const { dir, baseName } = getBasePath(filePath);
    outputPath.value = `${dir}/${baseName}_ocr.pdf`;
    splitOutputA.value = `${dir}/${baseName}_lang_a.pdf`;
    splitOutputB.value = `${dir}/${baseName}_lang_b.pdf`;

    log(`Input: ${filePath}`, "info");
  }
});

btnBrowseOutput.addEventListener("click", async () => {
  const filePath = await window.api.selectOutputFile(outputPath.value);
  if (filePath) {
    outputPath.value = filePath;
  }
});

// ── Toggle Sections ──

splitEnabled.addEventListener("change", () => {
  splitSettings.classList.toggle("hidden", !splitEnabled.checked);
});

splitPattern.addEventListener("change", () => {
  splitCustom.classList.toggle("hidden", splitPattern.value !== "custom");
});

pagelabelsEnabled.addEventListener("change", () => {
  pagelabelsSettings.classList.toggle("hidden", !pagelabelsEnabled.checked);
});

pagelabelsPreset.addEventListener("change", () => {
  const isCustom = pagelabelsPreset.value === "custom";
  pagelabelsSimple.classList.toggle("hidden", isCustom);
  pagelabelsCustom.classList.toggle("hidden", !isCustom);
});

tocEnabled.addEventListener("change", () => {
  tocSettings.classList.toggle("hidden", !tocEnabled.checked);
});

// ── Language Selection ──

function getSelectedLanguages() {
  const langs = [];
  if (langGrc.checked) langs.push("grc");
  if (langLat.checked) langs.push("lat");
  if (langEng.checked) langs.push("eng");
  return langs.length > 0 ? langs.join("+") : "eng";
}

// ── Page Labels ──

function getPageLabels() {
  if (!pagelabelsEnabled.checked) return null;

  if (pagelabelsPreset.value === "roman-arabic") {
    const bodyStart = parseInt(pagelabelsBodyStart.value) || 1;
    const ranges = [{ start_page: 0, style: "roman_lower", start_number: 1 }];
    if (bodyStart > 1) {
      ranges.push({
        start_page: bodyStart - 1,
        style: "arabic",
        start_number: 1,
      });
    }
    return ranges;
  }

  // Custom ranges
  const rows = pagelabelsRanges.querySelectorAll(".pagelabel-row");
  const ranges = [];
  rows.forEach((row) => {
    const startPage = parseInt(row.querySelector(".pl-start").value) || 1;
    const style = row.querySelector(".pl-style").value;
    const startNum = parseInt(row.querySelector(".pl-startnum").value) || 1;
    ranges.push({
      start_page: startPage - 1,
      style,
      start_number: startNum,
    });
  });
  return ranges.length > 0 ? ranges : null;
}

function addPageLabelRow(startPage = 1, style = "arabic", startNum = 1) {
  const row = document.createElement("div");
  row.className = "pagelabel-row";
  row.innerHTML = `
    <span style="color:var(--text-secondary);font-size:12px;">Page</span>
    <input type="number" class="text-input pl-start" value="${startPage}" min="1" style="width:60px;">
    <select class="select-input pl-style">
      <option value="roman_lower" ${style === "roman_lower" ? "selected" : ""}>Roman (i,ii,iii)</option>
      <option value="roman_upper" ${style === "roman_upper" ? "selected" : ""}>Roman (I,II,III)</option>
      <option value="arabic" ${style === "arabic" ? "selected" : ""}>Arabic (1,2,3)</option>
    </select>
    <span style="color:var(--text-secondary);font-size:12px;">from</span>
    <input type="number" class="text-input pl-startnum" value="${startNum}" min="1" style="width:50px;">
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
    if (title) {
      entries.push({ title, page: page - 1, level });
    }
  });
  return entries.length > 0 ? entries : null;
}

function addTocEntry(title = "", page = 1, level = 0) {
  const row = document.createElement("div");
  row.className = "toc-entry-row";
  row.dataset.level = level;
  row.style.paddingLeft = `${level * 20}px`;
  row.innerHTML = `
    <button class="toc-indent-btn toc-outdent" title="Decrease indent">&lt;</button>
    <button class="toc-indent-btn toc-indent" title="Increase indent">&gt;</button>
    <span class="toc-level-indicator">L${level}</span>
    <input type="text" class="text-input toc-title" placeholder="Title" value="${escapeHtml(title)}">
    <input type="number" class="text-input toc-page" placeholder="Pg" value="${page}" min="1" style="width:60px;">
    <button class="toc-delete">&times;</button>
  `;

  const updateLevel = (newLevel) => {
    const clamped = Math.max(0, Math.min(3, newLevel));
    row.dataset.level = clamped;
    row.style.paddingLeft = `${clamped * 20}px`;
    row.querySelector(".toc-level-indicator").textContent = `L${clamped}`;
  };

  row.querySelector(".toc-outdent").addEventListener("click", () => {
    updateLevel(parseInt(row.dataset.level) - 1);
  });
  row.querySelector(".toc-indent").addEventListener("click", () => {
    updateLevel(parseInt(row.dataset.level) + 1);
  });
  row.querySelector(".toc-delete").addEventListener("click", () => row.remove());

  tocEntries.appendChild(row);
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

btnAddToc.addEventListener("click", () => addTocEntry());

btnImportToc.addEventListener("click", () => {
  tocImportArea.classList.toggle("hidden");
});

btnParseToc.addEventListener("click", () => {
  const text = tocImportText.value;
  if (!text.trim()) return;

  const lines = text.split("\n");
  for (const line of lines) {
    if (!line.trim()) continue;

    // Detect indent level by leading spaces/tabs
    const stripped = line.replace(/^\s+/, "");
    const indent = line.length - stripped.length;
    const level = Math.min(3, Math.floor(indent / 2));

    // Try to parse "Title ... PageNum" or "Title\tPageNum"
    const match = stripped.match(/^(.+?)[\s.…·\-_]+(\d+)\s*$/) || stripped.match(/^(.+?)\t+(\d+)\s*$/);
    if (match) {
      addTocEntry(match[1].trim(), parseInt(match[2]), level);
    } else {
      addTocEntry(stripped.trim(), 1, level);
    }
  }

  tocImportArea.classList.add("hidden");
  tocImportText.value = "";
  log(`[OK] Imported ${lines.filter((l) => l.trim()).length} TOC entries`, "ok");
});

// ── OCR Processing ──

function setupProgressListener() {
  removeProgressListener = window.api.onOcrProgress((data) => {
    if (data.current != null && data.total > 0) {
      const pct = Math.round((data.current / data.total) * 100);
      progressBar.style.width = `${pct}%`;
    }
    if (data.message) {
      progressText.textContent = data.message;
      log(data.message);
    }
    if (data.page_result) {
      const r = data.page_result;
      log(
        `  Page ${r.page}: ${r.words} words, confidence: ${r.confidence.toFixed(1)}%`,
        "ok"
      );
    }
  });
}

function cleanupProgress() {
  btnStart.disabled = false;
  btnCancel.disabled = true;
  if (removeProgressListener) {
    removeProgressListener();
    removeProgressListener = null;
  }
}

btnStart.addEventListener("click", async () => {
  const input = inputPath.value;
  if (!input) return;

  let output = outputPath.value;
  if (!output) {
    const { dir, baseName } = getBasePath(input);
    output = `${dir}/${baseName}_ocr.pdf`;
    outputPath.value = output;
  }

  const lang = getSelectedLanguages();
  const dpi = parseInt(dpiSelect.value);
  const isSplit = splitEnabled.checked;

  log("", "");
  log(`Starting OCR: lang=${lang}, dpi=${dpi}${isSplit ? " [bilingual split]" : ""}`, "info");

  // Update UI state
  btnStart.disabled = true;
  btnCancel.disabled = false;
  progressSection.classList.remove("hidden");
  progressBar.style.width = "0%";
  progressText.textContent = "Loading file...";

  setupProgressListener();

  try {
    if (isSplit) {
      // Bilingual split mode
      const langAPages =
        splitPattern.value === "custom" ? splitLangAPages.value || "odd" : "odd";
      const langBPages =
        splitPattern.value === "custom" ? splitLangBPages.value || "even" : "even";
      const commonPages = splitCommonPages.value || "";
      const outputA = splitOutputA.value || `${getBasePath(input).dir}/${getBasePath(input).baseName}_lang_a.pdf`;
      const outputB = splitOutputB.value || `${getBasePath(input).dir}/${getBasePath(input).baseName}_lang_b.pdf`;

      log(`Output A: ${outputA}`, "info");
      log(`Output B: ${outputB}`, "info");

      const result = await window.api.splitBilingual({
        input,
        output_a: outputA,
        output_b: outputB,
        lang,
        dpi,
        lang_a_pages: langAPages,
        lang_b_pages: langBPages,
        common_pages: commonPages,
      });

      progressBar.style.width = "100%";
      progressText.textContent = "Complete!";
      log(`[DONE] Language A: ${result.output_a} (${result.pages_a} pages)`, "ok");
      log(`[DONE] Language B: ${result.output_b} (${result.pages_b} pages)`, "ok");

      currentOutputPath = result.output_a;
      modalMessage.textContent = `A: ${result.output_a}\nB: ${result.output_b}`;
      modalOverlay.classList.remove("hidden");
    } else {
      // Standard OCR mode
      log(`Output: ${output}`, "info");

      const params = { input, output, lang, dpi };

      // Add page labels if enabled
      const pageLabels = getPageLabels();
      if (pageLabels) params.page_labels = pageLabels;

      // Add TOC if enabled
      const toc = getTocEntries();
      if (toc) params.toc = toc;

      const result = await window.api.startOcr(params);
      progressBar.style.width = "100%";
      progressText.textContent = "Complete!";
      log(`[DONE] Searchable PDF saved: ${result.output_path}`, "ok");

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
  try {
    await window.api.cancelOcr();
    log("[CANCELLED] OCR processing cancelled.", "warn");
  } catch (err) {
    log(`[ERROR] Cancel failed: ${err.message}`, "error");
  }
  cleanupProgress();
  progressText.textContent = "Cancelled";
});

// ── Modal ──

btnOpenFile.addEventListener("click", () => {
  window.api.openFile(currentOutputPath);
  modalOverlay.classList.add("hidden");
});

btnShowFolder.addEventListener("click", () => {
  window.api.showInFolder(currentOutputPath);
  modalOverlay.classList.add("hidden");
});

btnModalClose.addEventListener("click", () => {
  modalOverlay.classList.add("hidden");
});

modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) {
    modalOverlay.classList.add("hidden");
  }
});

// ── Clear Log ──

btnClearLog.addEventListener("click", () => {
  logOutput.innerHTML = "";
});

// ── Start ──

init();
