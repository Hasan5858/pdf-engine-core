let currentPage = 0;
let totalPages = 1;
let currentOrigUrl = null;
let currentCleanUrl = null;
let previewDebounce = null;
let pollInterval = null;

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("pdfFileInput");
const uploadFilename = document.getElementById("uploadFilename");
const uploadHint = document.getElementById("uploadHint");
const engineSelector = document.getElementById("engineSelector");
const engineDesc = document.getElementById("engineDesc");
const m1Controls = document.getElementById("m1Controls");
const btnExportPdf = document.getElementById("btnExportPdf");
const exportStatus = document.getElementById("exportStatus");
const targetPagesInput = document.getElementById("targetPagesInput");

const progressContainer = document.getElementById("progressContainer");
const progressBarFill = document.getElementById("progressBarFill");
const progressText = document.getElementById("progressText");
const progressPercent = document.getElementById("progressPercent");

// Spatial Margins
const sliderTopCrop = document.getElementById("sliderTopCrop");
const valTopCrop = document.getElementById("valTopCrop");
const sliderBottomCrop = document.getElementById("sliderBottomCrop");
const valBottomCrop = document.getElementById("valBottomCrop");
const sliderSideCrop = document.getElementById("sliderSideCrop");
const valSideCrop = document.getElementById("valSideCrop");

// Target Color Filter
const targetColorPicker = document.getElementById("targetColorPicker");
const targetColorHex = document.getElementById("targetColorHex");
const sliderTolerance = document.getElementById("sliderTolerance");
const valTolerance = document.getElementById("valTolerance");

// Smart Thresholds
const sliderWhiten = document.getElementById("sliderWhiten");
const valWhiten = document.getElementById("valWhiten");
const sliderTextDarken = document.getElementById("sliderTextDarken");
const valTextDarken = document.getElementById("valTextDarken");

// Flags
const chkCleanPink = document.getElementById("chkCleanPink");
const chkCleanYellow = document.getElementById("chkCleanYellow");
const chkCleanGrey = document.getElementById("chkCleanGrey");
const chkPreserveColor = document.getElementById("chkPreserveColor");
const chkDeletePromo = document.getElementById("chkDeletePromo");

const btnPrevPage = document.getElementById("btnPrevPage");
const btnNextPage = document.getElementById("btnNextPage");
const pageNumberInput = document.getElementById("pageNumberInput");
const pageTotalText = document.getElementById("pageTotalText");
const tabCleaned = document.getElementById("tabCleaned");
const tabOriginal = document.getElementById("tabOriginal");
const previewCanvas = document.getElementById("previewCanvas");
const emptyState = document.getElementById("emptyState");

const btnCheckUpdate = document.getElementById("btnCheckUpdate");
const updateText = document.getElementById("updateText");

// Presets from Original Project
const MODE_PRESETS = {
  m1_live: {
    topCropPct: 4.6, bottomCropPct: 91.5, sideCropPct: 3.8,
    tolerance: 28, bgWhitenBr: 165, textDarkenBr: 82,
    cleanPink: true, cleanYellow: true, cleanGrey: true, preserveColor: true,
    deletePromo: false
  },
  m9_boxes: {
    topCropPct: 0.0, bottomCropPct: 100.0, sideCropPct: 0.0,
    tolerance: 0, bgWhitenBr: 165, textDarkenBr: 80,
    cleanPink: true, cleanYellow: false, cleanGrey: true, preserveColor: true,
    deletePromo: false
  }
};

function applyPreset(preset) {
  sliderTopCrop.value = preset.topCropPct;
  valTopCrop.textContent = `${preset.topCropPct}%`;

  sliderBottomCrop.value = preset.bottomCropPct;
  valBottomCrop.textContent = `${preset.bottomCropPct}%`;

  sliderSideCrop.value = preset.sideCropPct;
  valSideCrop.textContent = `${preset.sideCropPct}%`;

  sliderTolerance.value = preset.tolerance;
  valTolerance.textContent = preset.tolerance;

  sliderWhiten.value = preset.bgWhitenBr;
  valWhiten.textContent = preset.bgWhitenBr;

  sliderTextDarken.value = preset.textDarkenBr;
  valTextDarken.textContent = preset.textDarkenBr;

  chkCleanPink.checked = preset.cleanPink;
  chkCleanYellow.checked = preset.cleanYellow;
  chkCleanGrey.checked = preset.cleanGrey;
  chkPreserveColor.checked = preset.preserveColor;
  chkDeletePromo.checked = preset.deletePromo;

  targetColorPicker.value = "#ec4899";
  targetColorHex.textContent = "#EC4899";
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.style.borderColor = "#38bdf8"; });
dropZone.addEventListener("dragleave", () => { dropZone.style.borderColor = ""; });
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.style.borderColor = "";
  if (e.dataTransfer.files.length > 0) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFileUpload(e.target.files[0]);
  }
});

function handleFileUpload(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    alert("Please select a valid PDF file.");
    return;
  }

  uploadFilename.textContent = file.name;
  uploadHint.textContent = "Loading pages...";
  
  const formData = new FormData();
  formData.append("file", file);

  fetch("/api/upload", {
    method: "POST",
    body: formData
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      totalPages = data.pages;
      currentPage = 0;
      updatePageNav();
      uploadHint.textContent = `${totalPages} pages loaded. Ready to clean.`;
      btnExportPdf.disabled = false;
      emptyState.style.display = "none";
      previewCanvas.style.display = "block";
      requestPreview();
    } else {
      alert("Error uploading PDF: " + (data.error || "Unknown"));
    }
  })
  .catch(err => {
    console.error(err);
    alert("Upload failed.");
  });
}

// Engine selection logic: Now M1 and M9 BOTH have full controls enabled!
engineSelector.addEventListener("change", () => {
  const mode = engineSelector.value;
  if (mode === "m1_live") {
    m1Controls.style.display = "block";
    engineDesc.textContent = "Interactive spectrum based on color and brightness with live real-time preview.";
    applyPreset(MODE_PRESETS.m1_live);
    schedulePreview();
  } else if (mode === "m9_boxes") {
    m1Controls.style.display = "block"; // Full controls visible for M9 as well!
    engineDesc.textContent = "M9 ACS Deep 2nd-Pass: Full-margin layout (0% crop), dark watermark suppression & text boost.";
    applyPreset(MODE_PRESETS.m9_boxes);
    schedulePreview();
  } else if (mode === "m13_stream") {
    m1Controls.style.display = "none";
    engineDesc.textContent = "M13: Instant lossless purge of duplicate ad pages & Telegram red watermark streams.";
  }
});

function bindSlider(slider, label, suffix = "") {
  slider.addEventListener("input", () => {
    label.textContent = slider.value + suffix;
    schedulePreview();
  });
}

bindSlider(sliderTopCrop, valTopCrop, "%");
bindSlider(sliderBottomCrop, valBottomCrop, "%");
bindSlider(sliderSideCrop, valSideCrop, "%");
bindSlider(sliderTolerance, valTolerance);
bindSlider(sliderWhiten, valWhiten);
bindSlider(sliderTextDarken, valTextDarken);

targetColorPicker.addEventListener("input", () => {
  targetColorHex.textContent = targetColorPicker.value.toUpperCase();
  schedulePreview();
});

// Eyedropper on Canvas click!
previewCanvas.addEventListener("click", (e) => {
  const rect = previewCanvas.getBoundingClientRect();
  const scaleX = previewCanvas.width / rect.width;
  const scaleY = previewCanvas.height / rect.height;
  const x = Math.floor((e.clientX - rect.left) * scaleX);
  const y = Math.floor((e.clientY - rect.top) * scaleY);

  const ctx = previewCanvas.getContext("2d");
  const pixel = ctx.getImageData(x, y, 1, 1).data;
  const hex = "#" + ((1 << 24) + (pixel[0] << 16) + (pixel[1] << 8) + pixel[2]).toString(16).slice(1).toUpperCase();
  
  targetColorPicker.value = hex;
  targetColorHex.textContent = hex;
  schedulePreview();
});

[chkCleanPink, chkCleanYellow, chkCleanGrey, chkPreserveColor, chkDeletePromo].forEach(chk => {
  chk.addEventListener("change", schedulePreview);
});

function schedulePreview() {
  if (previewDebounce) clearTimeout(previewDebounce);
  previewDebounce = setTimeout(requestPreview, 60);
}

function getOptions() {
  const topPct = parseFloat(sliderTopCrop.value) || 0.0;
  const bottomVal = parseFloat(sliderBottomCrop.value) || 100.0;
  const sidePct = parseFloat(sliderSideCrop.value) || 0.0;

  return {
    margin_top: topPct,
    margin_bottom: bottomVal,
    margin_left: sidePct,
    margin_right: sidePct,
    margin_sides: sidePct,
    tolerance: parseInt(sliderTolerance.value) || 0,
    target_color: targetColorPicker.value || "#ec4899",
    bg_whiten: parseInt(sliderWhiten.value) || 165,
    text_darken: parseInt(sliderTextDarken.value) || 80,
    clean_pink: chkCleanPink.checked,
    clean_yellow: chkCleanYellow.checked,
    clean_grey: chkCleanGrey.checked,
    preserve_color: chkPreserveColor.checked,
    delete_promo: chkDeletePromo.checked,
    target_pages: targetPagesInput.value.trim()
  };
}

let previewAbortController = null;

function requestPreview() {
  if (previewAbortController) {
    previewAbortController.abort();
  }
  previewAbortController = new AbortController();

  fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine: engineSelector.value, page: currentPage, options: getOptions() }),
    signal: previewAbortController.signal
  })
  .then(res => res.json())
  .then(data => {
    currentOrigUrl = data.orig;
    currentCleanUrl = data.clean;
    applyCurrentView();
  })
  .catch(err => {
    if (err.name !== "AbortError") {
      console.error(err);
    }
  });
}

function renderImageToCanvas(dataUrl) {
  if (!dataUrl) return;
  const img = new Image();
  img.onload = () => {
    previewCanvas.width = img.width;
    previewCanvas.height = img.height;
    const ctx = previewCanvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
  };
  img.src = dataUrl;
}

function applyCurrentView() {
  if (tabCleaned.classList.contains("active")) {
    renderImageToCanvas(currentCleanUrl);
  } else {
    renderImageToCanvas(currentOrigUrl);
  }
}

tabCleaned.addEventListener("click", () => {
  tabCleaned.classList.add("active");
  tabOriginal.classList.remove("active");
  applyCurrentView();
});

tabOriginal.addEventListener("click", () => {
  tabOriginal.classList.add("active");
  tabCleaned.classList.remove("active");
  applyCurrentView();
});

function jumpToPage(targetPageOneIndexed) {
  if (totalPages <= 0) return;
  let target = parseInt(targetPageOneIndexed, 10);
  if (isNaN(target)) {
    target = currentPage + 1;
  }
  if (target < 1) target = 1;
  if (target > totalPages) target = totalPages;

  const newIndex = target - 1;
  if (newIndex !== currentPage) {
    currentPage = newIndex;
    updatePageNav();
    requestPreview();
  } else {
    updatePageNav();
  }
}

if (pageNumberInput) {
  pageNumberInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      jumpToPage(pageNumberInput.value);
      pageNumberInput.blur();
    }
  });

  pageNumberInput.addEventListener("change", () => {
    jumpToPage(pageNumberInput.value);
  });
}

btnPrevPage.addEventListener("click", () => {
  if (currentPage > 0) {
    currentPage--;
    updatePageNav();
    requestPreview();
  }
});

btnNextPage.addEventListener("click", () => {
  if (currentPage < totalPages - 1) {
    currentPage++;
    updatePageNav();
    requestPreview();
  }
});

function updatePageNav() {
  if (pageNumberInput) {
    pageNumberInput.value = currentPage + 1;
    pageNumberInput.max = totalPages > 0 ? totalPages : 1;
    pageNumberInput.disabled = (totalPages <= 0);
  }
  if (pageTotalText) {
    pageTotalText.textContent = `/ ${totalPages > 0 ? totalPages : 1}`;
  }
  btnPrevPage.disabled = (currentPage === 0 || totalPages <= 0);
  btnNextPage.disabled = (currentPage >= totalPages - 1 || totalPages <= 0);
}

// Full PDF Export with Live Progress Bar
btnExportPdf.addEventListener("click", () => {
  btnExportPdf.disabled = true;
  exportStatus.textContent = "";
  progressContainer.style.display = "flex";
  progressBarFill.style.width = "0%";
  progressText.textContent = "Starting engine...";
  progressPercent.textContent = "0%";

  const engineId = engineSelector.value;
  fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      engine: engineId,
      options: getOptions()
    })
  })
  .then(res => res.json())
  .then(data => {
    if (data.started) {
      startProgressPolling();
    } else {
      btnExportPdf.disabled = false;
      progressContainer.style.display = "none";
      exportStatus.textContent = "Failed to start: " + (data.error || "Unknown");
      exportStatus.style.color = "#ef4444";
    }
  })
  .catch(err => {
    btnExportPdf.disabled = false;
    progressContainer.style.display = "none";
    exportStatus.textContent = "Processing failed.";
    exportStatus.style.color = "#ef4444";
  });
});

function startProgressPolling() {
  if (pollInterval) clearInterval(pollInterval);
  
  pollInterval = setInterval(() => {
    fetch("/api/progress")
    .then(res => res.json())
    .then(p => {
      progressBarFill.style.width = p.percent + "%";
      progressPercent.textContent = p.percent + "%";
      progressText.textContent = p.status;

      if (!p.is_processing) {
        clearInterval(pollInterval);
        btnExportPdf.disabled = false;
        
        if (p.result && p.result.success) {
          const res = p.result;
          let promoInfo = "";
          if (res.promo_pages_removed && res.promo_pages_removed.length > 0) {
            promoInfo = ` | 🗑️ Removed ${res.promo_pages_removed.length} promo page(s) (${res.promo_pages_removed.join(', ')})`;
          }
          exportStatus.textContent = `✅ Complete in ${res.elapsed}! Processed ${res.processed_pages || res.cleaned_pages || res.total_pages} pages${promoInfo}. Saved to: ${res.output_path}`;
          exportStatus.style.color = "#10b981";
        } else if (p.error) {
          exportStatus.textContent = "❌ Error: " + p.error;
          exportStatus.style.color = "#ef4444";
        }
      }
    })
    .catch(console.error);
  }, 250);
}

// Update & Sync Checker
btnCheckUpdate.addEventListener("click", () => {
  updateText.textContent = "Checking...";
  fetch("/api/check_update")
  .then(res => res.json())
  .then(data => {
    if (data.status === "ok") {
      updateText.textContent = data.updated_engines > 0 ? `Updated ${data.updated_engines} engines!` : "Up to date";
    } else {
      updateText.textContent = "Local engine ready";
    }
  })
  .catch(() => {
    updateText.textContent = "Offline mode";
  });
});
