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

const progressContainer = document.getElementById("progressContainer");
const progressBarFill = document.getElementById("progressBarFill");
const progressText = document.getElementById("progressText");
const progressPercent = document.getElementById("progressPercent");

const bgWhiten = document.getElementById("bgWhiten");
const valBgWhiten = document.getElementById("valBgWhiten");
const textDarken = document.getElementById("textDarken");
const valTextDarken = document.getElementById("valTextDarken");
const tolerance = document.getElementById("tolerance");
const valTol = document.getElementById("valTol");
const targetColorPicker = document.getElementById("targetColorPicker");
const targetColorHex = document.getElementById("targetColorHex");

const chkCleanPink = document.getElementById("chkCleanPink");
const chkCleanGrey = document.getElementById("chkCleanGrey");
const chkPreserveColor = document.getElementById("chkPreserveColor");

const mTop = document.getElementById("mTop");
const mBottom = document.getElementById("mBottom");
const mLeft = document.getElementById("mLeft");
const mRight = document.getElementById("mRight");

const btnPrevPage = document.getElementById("btnPrevPage");
const btnNextPage = document.getElementById("btnNextPage");
const pageIndicator = document.getElementById("pageIndicator");
const tabCleaned = document.getElementById("tabCleaned");
const tabOriginal = document.getElementById("tabOriginal");
const previewImg = document.getElementById("previewImg");
const emptyState = document.getElementById("emptyState");

const btnCheckUpdate = document.getElementById("btnCheckUpdate");
const updateText = document.getElementById("updateText");

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.style.borderColor = "#3b82f6"; });
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
      previewImg.style.display = "block";
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

engineSelector.addEventListener("change", () => {
  const mode = engineSelector.value;
  if (mode === "m1_live") {
    m1Controls.style.display = "block";
    engineDesc.textContent = "Interactive spectrum based on color and brightness with live real-time preview.";
  } else if (mode === "m9_boxes") {
    m1Controls.style.display = "none";
    engineDesc.textContent = "Profile 9: Automatic detection and erasure of thick promo boxes & dark stamps.";
  } else if (mode === "m13_stream") {
    m1Controls.style.display = "none";
    engineDesc.textContent = "Profile 13: Instant lossless purge of duplicate ad pages & Telegram red watermark streams.";
  }
});

function bindSlider(slider, label) {
  slider.addEventListener("input", () => {
    label.textContent = slider.value;
    schedulePreview();
  });
}
bindSlider(bgWhiten, valBgWhiten);
bindSlider(textDarken, valTextDarken);
bindSlider(tolerance, valTol);

targetColorPicker.addEventListener("input", () => {
  targetColorHex.value = targetColorPicker.value;
  schedulePreview();
});
targetColorHex.addEventListener("change", () => {
  targetColorPicker.value = targetColorHex.value;
  schedulePreview();
});

[chkCleanPink, chkCleanGrey, chkPreserveColor].forEach(chk => {
  chk.addEventListener("change", schedulePreview);
});

[mTop, mBottom, mLeft, mRight].forEach(m => {
  m.addEventListener("input", schedulePreview);
});

// Snappy 80ms preview response debounce
function schedulePreview() {
  if (previewDebounce) clearTimeout(previewDebounce);
  previewDebounce = setTimeout(requestPreview, 80);
}

function getOptions() {
  return {
    bg_whiten: parseInt(bgWhiten.value) || 165,
    text_darken: parseInt(textDarken.value) || 82,
    tolerance: parseInt(tolerance.value) || 28,
    target_color: targetColorHex.value || "#ec4899",
    clean_pink: chkCleanPink.checked,
    clean_grey: chkCleanGrey.checked,
    preserve_color: chkPreserveColor.checked,
    margin_top: parseFloat(mTop.value) || 0,
    margin_bottom: parseFloat(mBottom.value) || 0,
    margin_left: parseFloat(mLeft.value) || 0,
    margin_right: parseFloat(mRight.value) || 0
  };
}

function requestPreview() {
  fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page: currentPage, options: getOptions() })
  })
  .then(res => res.json())
  .then(data => {
    currentOrigUrl = data.orig;
    currentCleanUrl = data.clean;
    applyCurrentView();
  })
  .catch(console.error);
}

function applyCurrentView() {
  if (tabCleaned.classList.contains("active")) {
    if (currentCleanUrl) previewImg.src = currentCleanUrl;
  } else {
    if (currentOrigUrl) previewImg.src = currentOrigUrl;
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
  pageIndicator.textContent = `Page ${currentPage + 1} / ${totalPages}`;
  btnPrevPage.disabled = (currentPage === 0);
  btnNextPage.disabled = (currentPage >= totalPages - 1);
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
          exportStatus.textContent = `✅ Complete in ${p.result.elapsed}! Saved to: ${p.result.output_path}`;
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
