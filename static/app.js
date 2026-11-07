let currentPage = 0;
let totalPages = 1;
let currentOrigUrl = null;
let currentCleanUrl = null;
let previewDebounce = null;

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("pdfFileInput");
const uploadFilename = document.getElementById("uploadFilename");
const uploadHint = document.getElementById("uploadHint");
const engineSelector = document.getElementById("engineSelector");
const engineDesc = document.getElementById("engineDesc");
const m1Controls = document.getElementById("m1Controls");
const btnExportPdf = document.getElementById("btnExportPdf");
const exportStatus = document.getElementById("exportStatus");

const minBr = document.getElementById("minBrightness");
const maxBr = document.getElementById("maxBrightness");
const tolerance = document.getElementById("tolerance");
const valMinBr = document.getElementById("valMinBr");
const valMaxBr = document.getElementById("valMaxBr");
const valTol = document.getElementById("valTol");
const targetColorPicker = document.getElementById("targetColorPicker");
const targetColorHex = document.getElementById("targetColorHex");

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

// Initialize Dropzone
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
  uploadHint.textContent = "Uploading & loading pages...";
  
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

// Engine selection logic
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

// Slider & Margin Bindings
function bindSlider(slider, label) {
  slider.addEventListener("input", () => {
    label.textContent = slider.value;
    schedulePreview();
  });
}
bindSlider(minBr, valMinBr);
bindSlider(maxBr, valMaxBr);
bindSlider(tolerance, valTol);

targetColorPicker.addEventListener("input", () => {
  targetColorHex.value = targetColorPicker.value;
  schedulePreview();
});
targetColorHex.addEventListener("change", () => {
  targetColorPicker.value = targetColorHex.value;
  schedulePreview();
});

[mTop, mBottom, mLeft, mRight].forEach(m => {
  m.addEventListener("input", schedulePreview);
});

function schedulePreview() {
  if (previewDebounce) clearTimeout(previewDebounce);
  previewDebounce = setTimeout(requestPreview, 250);
}

function getOptions() {
  return {
    mode: "brightness",
    min_brightness: parseInt(minBr.value),
    max_brightness: parseInt(maxBr.value),
    tolerance: parseInt(tolerance.value),
    target_color: targetColorHex.value,
    margin_top: parseInt(mTop.value) || 0,
    margin_bottom: parseInt(mBottom.value) || 0,
    margin_left: parseInt(mLeft.value) || 0,
    margin_right: parseInt(mRight.value) || 0
  };
}

function requestPreview() {
  fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: jsonString({ page: currentPage, options: getOptions() })
  })
  .then(res => res.json())
  .then(data => {
    currentOrigUrl = data.orig;
    currentCleanUrl = data.clean;
    applyCurrentView();
  })
  .catch(console.error);
}

function jsonString(obj) {
  return JSON.stringify(obj);
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

// Page Navigation
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

// Full PDF Export
btnExportPdf.addEventListener("click", () => {
  btnExportPdf.disabled = true;
  exportStatus.textContent = "Processing entire PDF... please wait.";
  exportStatus.style.color = "#3b82f6";

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
    btnExportPdf.disabled = false;
    if (data.success) {
      exportStatus.textContent = `Done in ${data.elapsed}! Saved to: ${data.output_path}`;
      exportStatus.style.color = "#10b981";
    } else {
      exportStatus.textContent = "Error: " + (data.error || "Unknown error");
      exportStatus.style.color = "#ef4444";
    }
  })
  .catch(err => {
    btnExportPdf.disabled = false;
    exportStatus.textContent = "Processing failed.";
    exportStatus.style.color = "#ef4444";
  });
});

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
