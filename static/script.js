// main interactions: inline preview, EXIF overlay, tool panel, scan flow, gauge update
document.addEventListener('DOMContentLoaded', function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const inlinePreview = document.getElementById('inlinePreview');
  const exifOverlay = document.getElementById('exifOverlay');
  const exifBody = document.getElementById('exifBody');
  const useSample = document.getElementById('useSample');
  const scanBtn = document.getElementById('scanBtn');
  const btnClear = document.getElementById('btnClear');
  const toolSearch = document.getElementById('toolSearch');

  // drag/drop
  ['dragenter','dragover','dragleave','drop'].forEach(ev => {
    dropzone.addEventListener(ev, preventDefaults, false);
  });
  function preventDefaults(e){ e.preventDefault(); e.stopPropagation(); }

  dropzone.addEventListener('dragover', ()=> dropzone.classList.add('dragover'));
  dropzone.addEventListener('dragleave', ()=> dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e)=> {
    dropzone.classList.remove('dragover');
    const dt = e.dataTransfer; const files = dt.files;
    handleFiles(files);
  });

  dropzone.addEventListener('click', ()=> fileInput.click());
  fileInput.addEventListener('change', (e)=> handleFiles(e.target.files));

  function handleFiles(files){
    if(!files || files.length === 0) return;
    const f = files[0];
    previewFileInline(f);
    if(useSample) useSample.checked = false;
  }

  function previewFileInline(file){
    const reader = new FileReader();
    const showNameOnly = (txt) => {
      inlinePreview.innerHTML = `<div class="empty">Selected: <code>${escapeHtml(txt)}</code></div>`;
      hideExif();
    };

    if(file.type.startsWith('image/')){
      reader.onload = function(e){
        inlinePreview.innerHTML = `<img id="previewImg" src="${e.target.result}" alt="preview">`;
        const imgEl = document.getElementById('previewImg');
        if(window.EXIF && imgEl){
          EXIF.getData(imgEl, function(){
            const make = EXIF.getTag(this, "Make") || '';
            const model = EXIF.getTag(this, "Model") || '';
            const dt = EXIF.getTag(this, "DateTimeOriginal") || EXIF.getTag(this, "DateTime") || '';
            const lat = EXIF.getTag(this, "GPSLatitude");
            const lon = EXIF.getTag(this, "GPSLongitude");
            const latRef = EXIF.getTag(this, "GPSLatitudeRef") || '';
            const lonRef = EXIF.getTag(this, "GPSLongitudeRef") || '';
            let html = '';
            if(make || model) html += `<div><strong>Camera:</strong> ${escapeHtml(make+' '+model)}</div>`;
            if(dt) html += `<div><strong>Date:</strong> ${escapeHtml(dt)}</div>`;
            if(lat && lon){
              const latDec = dmsToDecimal(lat, latRef);
              const lonDec = dmsToDecimal(lon, lonRef);
              html += `<div><strong>GPS:</strong> ${latDec.toFixed(6)}, ${lonDec.toFixed(6)}</div>`;
            }
            if(!html) html = '<div class="muted small">No EXIF found</div>';
            exifBody.innerHTML = html;
            showExif();
          });
        } else {
          exifBody.innerHTML = '<div class="muted small">EXIF library missing</div>';
          showExif();
        }
      };
      reader.readAsDataURL(file);

    } else if(file.type.startsWith('video/')){
      reader.onload = function(e){
        inlinePreview.innerHTML = `<video controls id="previewVideo" src="${e.target.result}" style="max-width:100%;"></video>`;
        exifBody.innerHTML = '<div class="muted small">Video preview — use ffprobe for details</div>';
        showExif();
      };
      reader.readAsDataURL(file);

    } else {
      showNameOnly(file.name);
    }
  }

  function showExif(){ exifOverlay.classList.remove('hidden'); }
  function hideExif(){ exifOverlay.classList.add('hidden'); }

  function dmsToDecimal(dms, ref){
    try{
      const d = dms[0].numerator / dms[0].denominator;
      const m = dms[1].numerator / dms[1].denominator;
      const s = dms[2].numerator / dms[2].denominator;
      let dec = d + m/60 + s/3600;
      if(ref === 'S' || ref === 'W') dec = -dec;
      return dec;
    } catch(e){ return 0; }
  }

  function escapeHtml(s){ return String(s).replace(/[&<>"']/g, (c)=> ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  // Scan button: submit form - ensures file exists or sample selected
  if(scanBtn){
    scanBtn.addEventListener('click', ()=>{
      const hasFile = fileInput.files && fileInput.files.length > 0;
      const usingSample = useSample && useSample.checked;
      if(!hasFile && !usingSample){
        alert("Please upload a file or check 'Use sample file' before scanning.");
        return;
      }
      // submit form
      document.getElementById('scanForm').submit();
    });
  }

  // Clear
  if(btnClear){
    btnClear.addEventListener('click', ()=>{
      inlinePreview.innerHTML = `<div class="empty small">No file selected</div>`;
      fileInput.value = null;
      if(useSample) useSample.checked = false;
      hideExif();
      updateGauge && updateGauge(0);
    });
  }

  // tool panel interactions
  document.querySelectorAll('.tool-category').forEach(cat => {
    const head = cat.querySelector('.cat-head');
    const body = cat.querySelector('.cat-body');
    const toggleIcon = cat.querySelector('.toggle-btn i');
    body.style.maxHeight = body.scrollHeight + "px";
    body.style.opacity = 1;
    toggleIcon && (toggleIcon.style.transform = "rotate(0deg)");
    head.addEventListener('click', ()=> {
      if(body.style.maxHeight === "0px"){
        body.style.maxHeight = body.scrollHeight + "px";
        body.style.opacity = 1;
        toggleIcon && (toggleIcon.style.transform = "rotate(0deg)");
      } else {
        body.style.maxHeight = "0px"; body.style.opacity = 0;
        toggleIcon && (toggleIcon.style.transform = "rotate(-90deg)");
      }
    });
  });

  // Select all / none
  document.querySelectorAll('.select-all').forEach(btn=>{
    btn.addEventListener('click',(e)=>{
      e.stopPropagation();
      const cat = e.target.closest('.tool-category');
      cat.querySelectorAll('input[type="checkbox"]').forEach(cb=>cb.checked=true);
    });
  });
  document.querySelectorAll('.deselect-all').forEach(btn=>{
    btn.addEventListener('click',(e)=>{
      e.stopPropagation();
      const cat = e.target.closest('.tool-category');
      cat.querySelectorAll('input[type="checkbox"]').forEach(cb=>cb.checked=false);
    });
  });

  // search
  if(toolSearch){
    toolSearch.addEventListener('input', ()=>{
      const q = toolSearch.value.toLowerCase();
      document.querySelectorAll('.tool-row').forEach(row=>{
        const tool = row.dataset.tool.toLowerCase();
        row.style.display = tool.includes(q) ? "flex" : "none";
      });
    });
  }

  // gauge helper: update stroke and text
  window.updateGauge = function(value){
    const circle = document.querySelector('.circle');
    const percentageText = document.querySelector('.percentage');
    const pct = Math.max(0, Math.min(100, Number(value) || 0));
    const dash = `${pct}, 100`;
    if(circle) circle.setAttribute('stroke-dasharray', dash);
    if(percentageText) percentageText.textContent = `${pct}%`;
  };

  // If results page has server-side score in DOM, update gauge (results.html will call updateGauge too)
  try {
    const serverScore = parseInt(document.querySelector('.big-score')?.textContent);
    if(!isNaN(serverScore)) updateGauge(serverScore);
  } catch(e){}

});
