/* ── State ─────────────────────────────────────────────────── */
let video1 = null;
let video2 = null;
let segments1 = [];
let segments2 = [];

const COLOR_V1 = '#7c6af7';
const COLOR_V2 = '#f7a26a';

/* ── Helpers ───────────────────────────────────────────────── */
function fmt(sec) {
  const s = Math.floor(sec % 60);
  const m = Math.floor(sec / 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function showProgress(text) {
  document.getElementById('progress-overlay').removeAttribute('hidden');
  document.getElementById('progress-text').textContent = text;
}
function setProgressText(text) {
  document.getElementById('progress-text').textContent = text;
}
function hideProgress() {
  document.getElementById('progress-overlay').setAttribute('hidden', '');
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}

/* ── File uploads ──────────────────────────────────────────── */
function setupUpload(inputId, dropId, infoId, slot) {
  const input = document.getElementById(inputId);
  const drop  = document.getElementById(dropId);
  const info  = document.getElementById(infoId);

  drop.addEventListener('click', (e) => {
    if (!e.target.classList.contains('browse-btn')) input.click();
  });

  drop.addEventListener('dragover', (e) => {
    e.preventDefault();
    drop.classList.add('drag-over');
  });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag-over'));
  drop.addEventListener('drop', async (e) => {
    e.preventDefault();
    drop.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) await doUpload(file, slot, info, drop);
  });

  input.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (file) await doUpload(file, slot, info, drop);
  });
}

async function doUpload(file, slot, infoEl, dropEl) {
  showProgress(`Uploading ${file.name}…`);
  infoEl.innerHTML = '';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    if (slot === 1) video1 = data;
    else            video2 = data;

    infoEl.innerHTML = `
      <span class="file-name">${data.filename}</span>
      <span class="file-meta">${fmt(data.duration)} · ${data.width}×${data.height}</span>`;
    dropEl.classList.add('has-file');
    checkReady();
  } catch (e) {
    infoEl.innerHTML = `<span class="error-text">${e.message}</span>`;
  } finally {
    hideProgress();
  }
}

function checkReady() {
  document.getElementById('btn-detect').disabled = !(video1 && video2);
}

/* ── Threshold slider ──────────────────────────────────────── */
const slider = document.getElementById('threshold-slider');
const sliderVal = document.getElementById('threshold-value');
slider.addEventListener('input', () => {
  sliderVal.textContent = parseFloat(slider.value).toFixed(2);
});

/* ── Detect segments ───────────────────────────────────────── */
document.getElementById('btn-detect').addEventListener('click', async () => {
  if (!video1 || !video2) return;

  showProgress('Analyzing videos for logical segments…');
  const threshold = parseFloat(slider.value);

  try {
    const [d1, d2] = await Promise.all([
      apiPost('/api/detect', { file_id: video1.file_id, threshold, max_segments: 8 }),
      apiPost('/api/detect', { file_id: video2.file_id, threshold, max_segments: 6 }),
    ]);

    segments1 = d1.segments;
    segments2 = d2.segments;

    renderTimeline('timeline-v1', '🎬 Main Video', segments1, video1.duration, COLOR_V1);
    renderTimeline('timeline-v2', '🎞️ Insert Video', segments2, video2.duration, COLOR_V2);
    renderPreview();

    const sec = document.getElementById('step-segments');
    sec.removeAttribute('hidden');
    sec.scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    alert(`Detection failed: ${e.message}`);
  } finally {
    hideProgress();
  }
});

/* ── Timeline rendering ────────────────────────────────────── */
function renderTimeline(containerId, label, segments, totalDur, color) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  // Label row
  const lbl = document.createElement('div');
  lbl.className = 'timeline-label';
  lbl.textContent = `${label} — ${segments.length} segment${segments.length !== 1 ? 's' : ''}`;
  container.appendChild(lbl);

  // Bar
  const bar = document.createElement('div');
  bar.className = 'timeline-bar';
  segments.forEach((seg, i) => {
    const left  = (seg.start    / totalDur) * 100;
    const width = (seg.duration / totalDur) * 100;
    const opacity = 0.65 + (i % 2) * 0.35;
    const el = document.createElement('div');
    el.className = 'seg-block';
    el.style.cssText = `left:${left}%;width:${width}%;background:${color};opacity:${opacity}`;
    el.title = `Segment ${i + 1}: ${fmt(seg.start)} → ${fmt(seg.end)} (${fmt(seg.duration)})`;
    el.textContent = width > 4 ? (i + 1) : '';
    bar.appendChild(el);
  });
  container.appendChild(bar);

  // Chips
  const chips = document.createElement('div');
  chips.className = 'seg-chips';
  segments.forEach((seg, i) => {
    const chip = document.createElement('div');
    chip.className = 'seg-chip';
    chip.innerHTML = `
      <span class="seg-dot" style="background:${color}"></span>
      <span>${fmt(seg.start)} → ${fmt(seg.end)}</span>
      <span class="chip-dur">${fmt(seg.duration)}</span>`;
    chips.appendChild(chip);
  });
  container.appendChild(chips);
}

function renderPreview() {
  const bar = document.getElementById('preview-bar');
  bar.innerHTML = '';

  const n1 = segments1.length;
  const n2 = segments2.length;

  // Build interleaved sequence: v1[0], v2[0], v1[1], v2[1], ..., v1[N-1]
  const parts = [];
  for (let i = 0; i < n1; i++) {
    parts.push({ type: 'v1', seg: segments1[i] });
    if (i < n1 - 1 && n2 > 0) {
      parts.push({ type: 'v2', seg: segments2[i % n2] });
    }
  }

  const totalSec = parts.reduce((s, p) => s + p.seg.duration, 0);
  let cursor = 0;

  parts.forEach((p) => {
    const width = (p.seg.duration / totalSec) * 100;
    const left  = (cursor / totalSec) * 100;
    const color = p.type === 'v1' ? COLOR_V1 : COLOR_V2;
    const el = document.createElement('div');
    el.className = 'seg-block';
    el.style.cssText = `left:${left}%;width:${width}%;background:${color};opacity:0.88`;
    el.title = `${p.type === 'v1' ? 'Main' : 'Insert'} — ${fmt(p.seg.duration)}`;
    el.textContent = width > 3 ? (p.type === 'v1' ? 'M' : 'I') : '';
    bar.appendChild(el);
    cursor += p.seg.duration;
  });

  document.getElementById('total-dur').textContent =
    `Estimated total: ~${fmt(totalSec)}  ·  ${n1} main + ${Math.min(n1 - 1, n2)} insert segments`;
}

/* ── Merge ─────────────────────────────────────────────────── */
document.getElementById('btn-merge').addEventListener('click', async () => {
  showProgress('Starting merge job…');

  try {
    const { job_id } = await apiPost('/api/merge', {
      video1_id: video1.file_id,
      video2_id: video2.file_id,
      segments1,
      segments2,
    });
    await pollJob(job_id);
  } catch (e) {
    hideProgress();
    alert(`Merge error: ${e.message}`);
  }
});

async function pollJob(jobId) {
  const tick = async () => {
    const job = await fetch(`/api/status/${jobId}`).then((r) => r.json());

    if (job.status === 'done') {
      hideProgress();
      document.getElementById('download-link').href = `/api/download/${job.result_id}`;
      const sec = document.getElementById('step-result');
      sec.removeAttribute('hidden');
      sec.scrollIntoView({ behavior: 'smooth' });
    } else if (job.status === 'error') {
      hideProgress();
      alert(`Processing error: ${job.error}`);
    } else {
      setProgressText(`Processing… ${job.progress || 0}%`);
      setTimeout(tick, 1500);
    }
  };
  await tick();
}

/* ── Init ──────────────────────────────────────────────────── */
setupUpload('input-v1', 'drop-v1', 'info-v1', 1);
setupUpload('input-v2', 'drop-v2', 'info-v2', 2);
