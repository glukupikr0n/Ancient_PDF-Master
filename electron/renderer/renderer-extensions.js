// ── Upscale ──

const upscaleEnabled = document.getElementById("upscale-enabled");
const upscaleSettings = document.getElementById("upscale-settings");
const upscaleScale = document.getElementById("upscale-scale");
const upscaleScaleLabel = document.getElementById("upscale-scale-label");
const upscaleFormat = document.getElementById("upscale-format");
const upscaleOutput = document.getElementById("upscale-output");
const btnUpscaleBrowse = document.getElementById("btn-upscale-browse");
const btnStartUpscale = document.getElementById("btn-start-upscale");
const upscaleStatus = document.getElementById("upscale-status");
const inputPathInput = document.getElementById("input-path");
const dpiInput = document.getElementById("dpi-select");

if (upscaleEnabled) {
  upscaleEnabled.addEventListener("change", () => {
    upscaleSettings.classList.toggle("hidden", !upscaleEnabled.checked);
    updateUpscaleBtn();
  });
}

if (upscaleScale) {
  upscaleScale.addEventListener("input", () => {
    upscaleScaleLabel.textContent = `${upscaleScale.value}\u00d7`;
  });
}

if (btnUpscaleBrowse) {
  btnUpscaleBrowse.addEventListener("click", async () => {
    const fmt = upscaleFormat.value;
    const ext = fmt === "pdf" ? "pdf" : fmt === "jpg" ? "jpg" : fmt === "tiff" ? "tiff" : "png";
    const inputName = inputPathInput.value;
    const base = inputName
      ? inputName.replace(/\.[^.]+$/, `_${upscaleScale.value}x.${ext}`)
      : `upscaled_${upscaleScale.value}x.${ext}`;
    const path = await window.api.selectUpscaleOutput(base);
    if (path) upscaleOutput.value = path;
  });
}

function updateUpscaleBtn() {
  if (btnStartUpscale) {
    btnStartUpscale.disabled = !upscaleEnabled.checked || !inputPathInput.value.trim();
  }
}

if (inputPathInput) inputPathInput.addEventListener("input", updateUpscaleBtn);

if (btnStartUpscale) {
  btnStartUpscale.addEventListener("click", async () => {
    const inputFile = inputPathInput.value.trim();
    if (!inputFile) { log("[UPSCALE] No input file selected.", "error"); return; }

    const scale = parseFloat(upscaleScale.value);
    const fmt = upscaleFormat.value;

    let outPath = upscaleOutput.value.trim();
    if (!outPath) {
      const ext = fmt === "pdf" ? "pdf" : fmt === "jpg" ? "jpg" : fmt === "tiff" ? "tiff" : "png";
      outPath = inputFile.replace(/\.[^.]+$/, `_${scale}x.${ext}`);
    }

    btnStartUpscale.disabled = true;
    upscaleStatus.textContent = "Starting upscale...";
    upscaleStatus.style.color = "";

    const removeListener = window.api.onOcrProgress((data) => {
      if (data.message) upscaleStatus.textContent = data.message;
      if (data.current != null && data.total > 0) {
        upscaleStatus.textContent = `${data.message || "Processing..."} (${data.current}/${data.total})`;
      }
    });

    try {
      const dpi = parseInt(dpiInput?.value || "300", 10);
      const result = await window.api.startUpscale({
        input: inputFile,
        output: outPath,
        scale,
        dpi,
        format: fmt,
      });

      removeListener();
      btnStartUpscale.disabled = false;

      if (fmt === "pdf") {
        upscaleStatus.textContent = `Done \u2192 ${result.output_path}`;
        upscaleStatus.style.color = "#4ecdc4";
        log(`[UPSCALE] ${result.pages} page(s) at ${scale}\u00d7 \u2192 ${result.output_path}`, "ok");
      } else {
        upscaleStatus.textContent = `Done \u2192 ${result.output_dir} (${result.pages} files)`;
        upscaleStatus.style.color = "#4ecdc4";
        log(`[UPSCALE] ${result.pages} image(s) at ${scale}\u00d7 \u2192 ${result.output_dir}`, "ok");
      }
    } catch (err) {
      removeListener();
      btnStartUpscale.disabled = false;
      upscaleStatus.textContent = err.message;
      upscaleStatus.style.color = "#ff6b6b";
      log(`[ERROR] Upscale failed: ${err.message}`, "error");
    }
  });
}

// ── Dataset Browser ──

const datasetCatalog = document.getElementById("dataset-catalog");
const downloadedDatasetList = document.getElementById("downloaded-dataset-list");
const datasetProgressSection = document.getElementById("dataset-progress-section");
const datasetProgressBar = document.getElementById("dataset-progress-bar");
const datasetProgressText = document.getElementById("dataset-progress-text");

let datasetProgressCleanup = null;

function setupDatasetProgressListener() {
  if (datasetProgressCleanup) datasetProgressCleanup();
  datasetProgressCleanup = window.api.onOcrProgress((data) => {
    if (data.phase === "downloading" || data.phase === "converting") {
      datasetProgressSection.classList.remove("hidden");
      const msg = data.message || "";
      datasetProgressText.textContent = msg;
      if (data.total > 0) {
        const pct = data.phase === "downloading"
          ? Math.round((data.downloaded / data.total) * 100)
          : Math.round((data.current / data.total) * 100);
        datasetProgressBar.style.width = `${pct}%`;
      }
    }
  });
}

async function loadDatasetCatalog() {
  if (!datasetCatalog) return;
  try {
    const result = await window.api.listAvailableDatasets();
    const datasets = result?.datasets || [];
    if (!datasets.length) {
      datasetCatalog.innerHTML = '<div class="zone-hint">No datasets available</div>';
      return;
    }
    datasetCatalog.innerHTML = datasets.map((d) => {
      const langBadge = d.language === "grc"
        ? '<span style="background:#3a7ca5;padding:1px 5px;border-radius:3px;font-size:10px;">Greek</span>'
        : '<span style="background:#8a5c2a;padding:1px 5px;border-radius:3px;font-size:10px;">Latin</span>';
      const srcBadge = d.source === "lace"
        ? '<span style="background:#5a3a7a;padding:1px 5px;border-radius:3px;font-size:10px;">Lace</span>'
        : '<span style="background:#2a6a4a;padding:1px 5px;border-radius:3px;font-size:10px;">OGL</span>';
      return `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 8px;margin-bottom:4px;background:rgba(255,255,255,0.03);border-radius:6px;">
          <div style="flex:1;min-width:0;">
            <div style="font-size:12px;font-weight:600;">${d.name} ${langBadge} ${srcBadge}</div>
            <div style="font-size:10px;opacity:0.6;margin-top:2px;">${d.description}</div>
            <div style="font-size:10px;opacity:0.5;">~${d.estimated_size_mb}MB &middot; ~${d.pair_count_estimate} pairs</div>
          </div>
          <button class="btn-small" data-dataset-id="${d.id}" data-dataset-source="${d.source}" onclick="downloadAndConvertDataset(this)">Download</button>
        </div>
      `;
    }).join("");
  } catch (err) {
    datasetCatalog.innerHTML = `<div class="zone-hint" style="color:#ff6b6b;">${err.message}</div>`;
  }
}

async function refreshDownloadedDatasets() {
  if (!downloadedDatasetList) return;
  try {
    const result = await window.api.listDownloadedDatasets();
    const datasets = result?.datasets || [];
    if (!datasets.length) {
      downloadedDatasetList.innerHTML = "None yet";
      return;
    }
    downloadedDatasetList.innerHTML = datasets.map((d) => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 6px;margin-bottom:3px;background:rgba(255,255,255,0.03);border-radius:4px;">
        <span style="font-size:11px;">${d.name || d.id} (${d.files_count || "?"} files)</span>
        <div style="display:flex;gap:4px;">
          <button class="btn-small" onclick="convertDownloadedDataset('${d.id}', '${d.path}', '${d.source}')">Convert</button>
          <button class="btn-small" style="color:#ff6b6b;" onclick="deleteDownloadedDataset('${d.id}')">Delete</button>
        </div>
      </div>
    `).join("");
  } catch {
    downloadedDatasetList.innerHTML = "Error loading";
  }
}

// eslint-disable-next-line no-unused-vars
async function downloadAndConvertDataset(btn) {
  const datasetId = btn.dataset.datasetId;
  const source = btn.dataset.datasetSource;
  btn.disabled = true;
  btn.textContent = "Downloading...";

  setupDatasetProgressListener();
  datasetProgressSection.classList.remove("hidden");

  try {
    const dlResult = await window.api.downloadDataset({ dataset_id: datasetId });
    log(`Dataset downloaded: ${dlResult.files_count} files`, "info");

    const outputDir = await window.api.selectDatasetOutputDir();
    if (!outputDir) {
      btn.disabled = false;
      btn.textContent = "Download";
      datasetProgressSection.classList.add("hidden");
      return;
    }

    btn.textContent = "Converting...";
    datasetProgressText.textContent = "Converting to training format...";
    const convResult = await window.api.convertDataset({
      dataset_id: datasetId,
      source_dir: dlResult.path,
      output_dir: outputDir,
      source: source,
      mode: "synthetic",
    });

    const pairs = convResult.pairs || 0;
    log(`Dataset converted: ${pairs} training pairs in ${outputDir}`, "info");
    datasetProgressText.textContent = `Done! ${pairs} training pairs created.`;
    datasetProgressBar.style.width = "100%";

    const trainDataDir = document.getElementById("train-data-dir");
    if (trainDataDir) {
      trainDataDir.value = outputDir;
      trainDataDir.dispatchEvent(new Event("change"));
    }

    await refreshDownloadedDatasets();
  } catch (err) {
    log(`Dataset error: ${err.message}`, "error");
    datasetProgressText.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Download";
    if (datasetProgressCleanup) { datasetProgressCleanup(); datasetProgressCleanup = null; }
  }
}

// eslint-disable-next-line no-unused-vars
async function convertDownloadedDataset(datasetId, sourcePath, source) {
  const outputDir = await window.api.selectDatasetOutputDir();
  if (!outputDir) return;

  setupDatasetProgressListener();
  datasetProgressSection.classList.remove("hidden");

  try {
    const result = await window.api.convertDataset({
      dataset_id: datasetId,
      source_dir: sourcePath,
      output_dir: outputDir,
      source: source,
      mode: "synthetic",
    });
    const pairs = result.pairs || 0;
    log(`Converted: ${pairs} training pairs`, "info");
    datasetProgressText.textContent = `Done! ${pairs} pairs.`;

    const trainDataDir = document.getElementById("train-data-dir");
    if (trainDataDir) {
      trainDataDir.value = outputDir;
      trainDataDir.dispatchEvent(new Event("change"));
    }
  } catch (err) {
    log(`Convert error: ${err.message}`, "error");
    datasetProgressText.textContent = `Error: ${err.message}`;
  } finally {
    if (datasetProgressCleanup) { datasetProgressCleanup(); datasetProgressCleanup = null; }
  }
}

// eslint-disable-next-line no-unused-vars
async function deleteDownloadedDataset(datasetId) {
  try {
    await window.api.deleteDataset({ dataset_id: datasetId });
    log(`Dataset deleted: ${datasetId}`, "info");
    await refreshDownloadedDatasets();
  } catch (err) {
    log(`Delete error: ${err.message}`, "error");
  }
}

// ── Init extensions ──
loadDatasetCatalog();
refreshDownloadedDatasets();
