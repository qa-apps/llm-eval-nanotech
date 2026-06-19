/* ── State ─────────────────────────────────────────────────── */
let video1    = null;
let video2    = null;
let segments1 = [];
let segments2 = [];
let aiStrategy = "rapid_interleave";

const COLOR_V1 = '#7c6af7';
const COLOR_V2 = '#f7a26a';

const STRATEGY_DESC = {
  rapid_interleave:  'M I M I M I … M — insert between every main segment',
  spaced_interleave: 'M M I M M I … M — insert every second gap',
  bookend:           'I  M M M … M  I — insert wraps the main sequence',
  sandwich:          'M  I I I … I  M — inserts clustered in the middle',
};

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
    infoEl.innerHTML = `<span class="error-text">Upload failed: ${e.message}</span>`;
  } finally {
    hideProgress();
  }
}

function checkReady() {
  const ready = !!(video1 && video2);
  document.getElementById('btn-detect').disabled = !ready;
  document.getElementById('btn-ask-ai').disabled = !ready;
}

/* ── Threshold slider ──────────────────────────────────────── */
const slider = document.getElementById('threshold-slider');
const sliderVal = document.getElementById('threshold-value');
slider.addEventListener('input', () => {
  sliderVal.textContent = parseFloat(slider.value).toFixed(2);
});

/* ── AI Director ───────────────────────────────────────────── */
document.getElementById('btn-ask-ai').addEventListener('click', async () => {
  const goal = document.getElementById('goal-input').value.trim();
  if (!goal) {
    document.getElementById('goal-input').focus();
    return;
  }

  showProgress('Asking AI Director (nanotech.icu)…');

  try {
    const g = await apiPost('/api/ai-guide', { goal });
    applyAiGuidance(g);
  } catch (e) {
    alert(`AI Director unavailable: ${e.message}\nYou can still adjust settings manually.`);
  } finally {
    hideProgress();
  }
});

function applyAiGuidance(g) {
  // Update slider
  slider.value = g.threshold;
  sliderVal.textContent = parseFloat(g.threshold).toFixed(2);

  // Set strategy
  aiStrategy = g.strategy || 'rapid_interleave';
  setActiveStrategy(aiStrategy);

  // Show result card
  const card = document.getElementById('ai-result');
  card.removeAttribute('hidden');

  document.getElementById('mood-chip').textContent = g.mood || 'auto';
  document.getElementById('ai-model-label').textContent = g.model ? `via ${g.model}` : '';
  document.getElementById('ai-brief').textContent = g.brief || '';

  document.getElementById('ai-params').innerHTML = `
    <span class="param-chip">threshold <strong>${parseFloat(g.threshold).toFixed(2)}</strong></span>
    <span class="param-chip">main segments <strong>${g.max_segments_v1}</strong></span>
    <span class="param-chip">insert segments <strong>${g.max_segments_v2}</strong></span>
    <span class="param-chip">strategy <strong>${(g.strategy || '').replace(/_/g, ' ')}</strong></span>
  `;

  // Store AI-suggested segment counts for detect call
  document.getElementById('btn-detect').dataset.maxV1 = g.max_segments_v1;
  document.getElementById('btn-detect').dataset.maxV2 = g.max_segments_v2;
}

/* ── Strategy selector ─────────────────────────────────────── */
document.getElementById('strategy-btns').addEventListener('click', (e) => {
  const btn = e.target.closest('.strat-btn');
  if (!btn) return;
  setActiveStrategy(btn.dataset.strat);
});

function setActiveStrategy(strat) {
  aiStrategy = strat;
  document.querySelectorAll('.strat-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.strat === strat);
  });
  const desc = document.getElementById('strat-desc');
  if (desc) desc.textContent = STRATEGY_DESC[strat] || '';
  if (segments1.length) renderPreview();
}

/* ── Detect segments ───────────────────────────────────────── */
document.getElementById('btn-detect').addEventListener('click', async () => {
  if (!video1 || !video2) return;

  const threshold = parseFloat(slider.value);
  const detectBtn = document.getElementById('btn-detect');
  const maxV1 = parseInt(detectBtn.dataset.maxV1 || '8');
  const maxV2 = parseInt(detectBtn.dataset.maxV2 || '6');

  showProgress('Analyzing videos for logical segments…');

  try {
    const [d1, d2] = await Promise.all([
      apiPost('/api/detect', { file_id: video1.file_id, threshold, max_segments: maxV1 }),
      apiPost('/api/detect', { file_id: video2.file_id, threshold, max_segments: maxV2 }),
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

  const lbl = document.createElement('div');
  lbl.className = 'timeline-label';
  lbl.textContent = `${label} — ${segments.length} segment${segments.length !== 1 ? 's' : ''}`;
  container.appendChild(lbl);

  const bar = document.createElement('div');
  bar.className = 'timeline-bar';
  segments.forEach((seg, i) => {
    const left  = (seg.start    / totalDur) * 100;
    const width = (seg.duration / totalDur) * 100;
    const el = document.createElement('div');
    el.className = 'seg-block';
    el.style.cssText = `left:${left}%;width:${width}%;background:${color};opacity:${0.65 + (i%2)*0.35}`;
    el.title = `Segment ${i+1}: ${fmt(seg.start)} → ${fmt(seg.end)} (${fmt(seg.duration)})`;
    el.textContent = width > 4 ? (i + 1) : '';
    bar.appendChild(el);
  });
  container.appendChild(bar);

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

function buildOrder(segs1, segs2, strategy) {
  const n1 = segs1.length, n2 = segs2.length;
  const order = [];

  if (strategy === 'bookend') {
    if (n2 > 0)                        order.push({ type: 'v2', seg: segs2[0] });
    segs1.forEach(s =>                 order.push({ type: 'v1', seg: s }));
    if (n2 > 1)                        order.push({ type: 'v2', seg: segs2[n2-1] });
    else if (n2 === 1)                 order.push({ type: 'v2', seg: segs2[0] });
  } else if (strategy === 'sandwich') {
    if (n1 > 0)                        order.push({ type: 'v1', seg: segs1[0] });
    segs2.forEach(s =>                 order.push({ type: 'v2', seg: s }));
    if (n1 > 1)                        order.push({ type: 'v1', seg: segs1[n1-1] });
  } else if (strategy === 'spaced_interleave') {
    let v2i = 0;
    segs1.forEach((seg, i) => {
      order.push({ type: 'v1', seg });
      if ((i % 2 === 1) && n2 > 0) {
        order.push({ type: 'v2', seg: segs2[v2i++ % n2] });
      }
    });
  } else {
    segs1.forEach((seg, i) => {
      order.push({ type: 'v1', seg });
      if (i < n1 - 1 && n2 > 0) order.push({ type: 'v2', seg: segs2[i % n2] });
    });
  }
  return order;
}

function renderPreview() {
  const bar = document.getElementById('preview-bar');
  bar.innerHTML = '';

  const order    = buildOrder(segments1, segments2, aiStrategy);
  const totalSec = order.reduce((s, p) => s + p.seg.duration, 0);
  let cursor = 0;

  order.forEach((p) => {
    const width = (p.seg.duration / totalSec) * 100;
    const left  = (cursor / totalSec) * 100;
    const el = document.createElement('div');
    el.className = 'seg-block';
    el.style.cssText = `left:${left}%;width:${width}%;background:${p.type==='v1'?COLOR_V1:COLOR_V2};opacity:0.88`;
    el.title = `${p.type==='v1'?'Main':'Insert'} — ${fmt(p.seg.duration)}`;
    el.textContent = width > 3 ? (p.type === 'v1' ? 'M' : 'I') : '';
    bar.appendChild(el);
    cursor += p.seg.duration;
  });

  const insertCount = order.filter(p => p.type === 'v2').length;
  document.getElementById('total-dur').textContent =
    `~${fmt(totalSec)} total · ${segments1.length} main + ${insertCount} insert · strategy: ${aiStrategy.replace(/_/g,' ')}`;
}

/* ── Merge ─────────────────────────────────────────────────── */
document.getElementById('btn-merge').addEventListener('click', async () => {
  showProgress('Starting merge…');
  try {
    const { job_id } = await apiPost('/api/merge', {
      video1_id: video1.file_id,
      video2_id: video2.file_id,
      segments1,
      segments2,
      strategy: aiStrategy,
    });
    await pollJob(job_id);
  } catch (e) {
    hideProgress();
    alert(`Merge error: ${e.message}`);
  }
});

async function pollJob(jobId) {
  const tick = async () => {
    const job = await fetch(`/api/status/${jobId}`).then(r => r.json());
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
      setProgressText(`Processing video… ${job.progress || 0}%`);
      setTimeout(tick, 1500);
    }
  };
  await tick();
}

/* ── Init ──────────────────────────────────────────────────── */
setupUpload('input-v1', 'drop-v1', 'info-v1', 1);
setupUpload('input-v2', 'drop-v2', 'info-v2', 2);
