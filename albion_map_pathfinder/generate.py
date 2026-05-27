"""Generate the Albion Map Pathfinding web app HTML file."""

html_content = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Albion Online Map Pathfinding</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; }
.app { display: flex; height: 100vh; }
.canvas-container { flex: 1; position: relative; overflow: hidden; background: #0d1b2a; }
canvas { display: block; cursor: crosshair; }
.sidebar { width: 350px; background: #16213e; border-left: 1px solid #2a3f5f; display: flex; flex-direction: column; overflow-y: auto; }
.panel { border-bottom: 1px solid #2a3f5f; }
.panel-header { padding: 12px 16px; background: #1a1a2e; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 14px; }
.panel-header:hover { background: #243b55; }
.panel-body { padding: 12px 16px; display: none; }
.panel-body.open { display: block; }
.zone-search { width: 100%; padding: 8px 12px; border: 1px solid #2a3f5f; border-radius: 4px; background: #0f1a2e; color: #e0e0e0; font-size: 13px; margin-bottom: 8px; }
.zone-search:focus { outline: none; border-color: #4a9eff; }
.search-results { max-height: 200px; overflow-y: auto; }
.search-item { padding: 6px 8px; cursor: pointer; font-size: 13px; border-radius: 3px; display: flex; justify-content: space-between; align-items: center; }
.search-item:hover { background: #243b55; }
.search-item .pvp-badge { font-size: 11px; padding: 2px 6px; border-radius: 2px; }
.pvp-blue { background: #1565c0; color: #fff; }
.pvp-yellow { background: #f57f17; color: #000; }
.pvp-red { background: #c62828; color: #fff; }
.pvp-black { background: #6a1b9a; color: #fff; }
.pvp-highway { background: #e65100; color: #fff; }
.weight-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.weight-row label { font-size: 13px; }
.weight-row input[type="range"] { width: 150px; accent-color: #4a9eff; }
.weight-row .val { font-size: 12px; color: #4a9eff; width: 30px; text-align: right; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 13px; transition: background 0.2s; }
.btn-primary { background: #4a9eff; color: #fff; }
.btn-primary:hover { background: #3a8eef; }
.btn-secondary { background: #2a3f5f; color: #e0e0e0; }
.btn-secondary:hover { background: #3a5f7f; }
.btn-group { display: flex; gap: 8px; margin-top: 8px; }
.point-display { display: flex; gap: 8px; margin-bottom: 12px; }
.point-box { flex: 1; padding: 8px; border-radius: 4px; background: #0f1a2e; border: 1px solid #2a3f5f; min-height: 52px; }
.point-box.start { border-color: #4caf50; }
.point-box.end { border-color: #ff5722; }
.point-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.point-box.start .point-label { color: #4caf50; }
.point-box.end .point-label { color: #ff5722; }
.point-zone { font-size: 12px; }
.route-summary { background: #0f1a2e; border-radius: 4px; padding: 12px; border: 1px solid #2a3f5f; }
.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.summary-item { text-align: center; }
.summary-value { font-size: 20px; font-weight: bold; color: #4a9eff; }
.summary-label { font-size: 11px; color: #888; text-transform: uppercase; margin-top: 2px; }
.zone-breakdown { margin-top: 8px; }
.zone-breakdown-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.zone-bar { display: flex; height: 24px; border-radius: 4px; overflow: hidden; margin-bottom: 4px; }
.zone-bar-segment { display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; color: #fff; min-width: 0; }
.zone-bar-segment.blue { background: #2196f3; }
.zone-bar-segment.yellow { background: #ffc107; color: #000; }
.zone-bar-segment.red { background: #f44336; }
.zone-bar-segment.black { background: #9c27b0; }
.zone-bar-segment.highway { background: #ff9800; }
.zone-bar-legend { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.zone-bar-legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; }
.zone-bar-legend-color { width: 12px; height: 12px; border-radius: 2px; }
.path-steps { max-height: 200px; overflow-y: auto; font-size: 12px; }
.path-step { padding: 4px 8px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a3f5f; }
.path-step:last-child { border-bottom: none; }
.path-step-name { flex: 1; }
.path-step-badge { font-size: 10px; padding: 1px 4px; border-radius: 2px; margin-left: 8px; }
.instructions { font-size: 12px; color: #888; line-height: 1.5; padding: 8px; background: #0f1a2e; border-radius: 4px; margin: 8px 0; }
.status-bar { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); padding: 4px 12px; font-size: 12px; color: #ccc; display: flex; justify-content: space-between; }
legend-item { display: flex; align-items: center; gap: 4px; font-size: 11px; }
.legend-color { width: 12px; height: 12px; border-radius: 2px; }
.legend-color.blue { background: #2196f3; }
.legend-color.yellow { background: #ffc107; }
.legend-color.red { background: #f44336; }
.legend-color.black { background: #9c27b0; }
.legend-color.start { background: #4caf50; }
.legend-color.end { background: #ff5722; }
.legend-color.route-color { background: #00e676; }
</style>
</head>
<body>
<div class="app">
<div class="canvas-container" id="canvasContainer">
  <canvas id="mapCanvas"></canvas>
  <div class="status-bar">
    <span id="statusText">Scroll to zoom | Drag to pan | Click for start/end</span>
    <span id="zoneCount"></span>
  </div>
</div>
<div class="sidebar">
<div class="panel"><div class="panel-header">Route</div><div class="panel-body open">
  <div class="point-display">
    <div class="point-box start"><div class="point-label">Start</div><div class="point-zone" id="startName">Click on map</div></div>
    <div class="point-box end"><div class="point-label">End</div><div class="point-zone" id="endName">Click on map</div></div>
  </div>
  <div class="btn-group">
    <button class="btn btn-primary" onclick="calculatePath()">Calculate Route</button>
    <button class="btn btn-secondary" onclick="clearRoute()">Clear</button>
  </div>
</div></div>
<div class="panel"><div class="panel-header">Find Zone</div><div class="panel-body open">
  <input type="text" class="zone-search" id="zoneSearch" placeholder="Search zone name...">
  <div class="search-results" id="searchResults"></div>
</div></div>
<div class="panel"><div class="panel-header">Zone Weights</div><div class="panel-body open">
  <div class="weight-row"><label>Blue</label><input type="range" id="weightBlue" min="1" max="10" value="1"><span class="val" id="valBlue">1</span></div>
  <div class="weight-row"><label>Yellow</label><input type="range" id="weightYellow" min="1" max="10" value="3"><span class="val" id="valYellow">3</span></div>
  <div class="weight-row"><label>Red</label><input type="range" id="weightRed" min="1" max="10" value="5"><span class="val" id="valRed">5</span></div>
  <div class="weight-row"><label>Black</label><input type="range" id="weightBlack" min="1" max="10" value="8"><span class="val" id="valBlack">8</span></div>
  <div class="weight-row"><label>Highway</label><input type="range" id="weightHighway" min="1" max="10" value="2"><span class="val" id="valHighway">2</span></div>
</div></div>
<div class="panel"><div class="panel-header">Route Summary</div><div class="panel-body open">
  <div class="route-summary" id="routeSummary" style="display:none">
    <div class="summary-grid">
      <div class="summary-item"><div class="summary-value" id="sumDistance">0</div><div class="summary-label">Distance</div></div>
      <div class="summary-item"><div class="summary-value" id="sumZones">0</div><div class="summary-label">Zones</div></div>
      <div class="summary-item"><div class="summary-value" id="sumTime">0m</div><div class="summary-label">Est. Time</div></div>
      <div class="summary-item"><div class="summary-value" id="sumWeighted">0</div><div class="summary-label">Weighted Cost</div></div>
    </div>
    <div class="zone-breakdown"><div class="zone-breakdown-title">Zone Breakdown</div><div id="breakdownText"></div><div class="zone-bar" id="zoneBar"></div><div class="zone-bar-legend" id="barLegend"></div></div>
    <div class="zone-breakdown" style="margin-top:12px"><div class="zone-breakdown-title">Path Steps</div><div id="pathSteps" class="path-steps"></div></div>
  </div>
  <div id="noRouteMsg" class="instructions">Click on the map to set Start (green) and End (orange), then click "Calculate Route". First click sets start, second sets end. Click start again to reset.</div>
</div></div>
<div class="panel"><div class="panel-header">Legend</div><div class="panel-body open">
  <div class="zone-bar-legend">
    <div class="legend-item"><div class="legend-color blue"></div> Blue Zone</div>
    <div class="legend-item"><div class="legend-color yellow"></div> Yellow Zone</div>
    <div class="legend-item"><div class="legend-color red"></div> Red Zone</div>
    <div class="legend-item"><div class="legend-color black"></div> Black Zone</div>
    <div class="legend-item"><div class="legend-color start"></div> Start</div>
    <div class="legend-item"><div class="legend-color end"></div> End</div>
    <div class="legend-item"><div class="legend-color route-color"></div> Route</div>
  </div>
</div></div>
</div>
</div>
<script>
let zones = [];
let zoneMap = {};
let canvas, ctx, container;
let scale = 1, offsetX = 0, offsetY = 0;
let isDragging = false, dragStartX = 0, dragStartY = 0, oldOffsetX = 0, oldOffsetY = 0;
let selectedStart = null, selectedEnd = null;
let currentRoute = null;
let hoveredZone = null;
let minX = 0, maxX = 0, minY = 0, maxY = 0, mapW = 0, mapH = 0;

const PVP_COLORS = {blue:'#2196f3',yellow:'#ffc107',red:'#f44336',black:'#9c27b0',highway:'#ff9800',city:'#64b5f6'};

async function init() {
  canvas = document.getElementById('mapCanvas');
  ctx = canvas.getContext('2d');
  container = document.getElementById('canvasContainer');
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  try {
    zones = await fetch('data/zones_complete.json').then(r => r.json());
    zoneMap = {};
    zones.forEach(z => { if(z.id !== undefined) zoneMap[z.id] = z; });
    document.getElementById('zoneCount').textContent = zones.length + ' zones';
    calculateBounds();
    fitToView();
    setupEventListeners();
    setupWeights();
    setupSearch();
    render();
  } catch(e) { console.error('Failed to load zones:', e); }
}

function resizeCanvas() {
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
  render();
}

function calculateBounds() {
  if(!zones.length) return;
  const xs = zones.map(z => z.x);
  const ys = zones.map(z => z.y);
  minX = Math.min(...xs); maxX = Math.max(...xs);
  minY = Math.min(...ys); maxY = Math.max(...ys);
  mapW = maxX - minX; mapH = maxY - minY;
}

function fitToView() {
  const pad = 50;
  const sx = canvas.width / (mapW + pad * 2);
  const sy = canvas.height / (mapH + pad * 2);
  scale = Math.min(sx, sy) * 0.9;
  offsetX = canvas.width / 2;
  offsetY = canvas.height / 2;
}

function worldToScreen(x, y) {
  return {
    sx: (x - (minX + maxX) / 2) * scale + offsetX,
    sy: -(y - (minY + maxY) / 2) * scale + offsetY
  };
}

function screenToWorld(sx, sy) {
  return {
    x: (sx - offsetX) / scale + (minX + maxX) / 2,
    y: -(sy - offsetY) / scale + (minY + maxY) / 2
  };
}

function render() {
  ctx.fillStyle = '#0d1b2a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if(!zones.length) {
    ctx.fillStyle = '#fff';
    ctx.font = '16px sans-serif';
    ctx.fillText('Loading zones...', 20, 20);
    return;
  }
  drawGrid();
  drawConnections();
  if(currentRoute) drawRoutePath();
  drawZoneMarkers();
  drawStartEnd();
  if(hoveredZone) drawHoverLabel();
}

function drawGrid() {
  ctx.strokeStyle = '#1a2a40';
  ctx.lineWidth = 0.5;
  const step = 50;
  const tl = screenToWorld(0, 0);
  const br = screenToWorld(canvas.width, canvas.height);
  for(let x = Math.floor(tl.x / step) * step; x <= br.x; x += step) {
    const s1 = worldToScreen(x, tl.y);
    const s2 = worldToScreen(x, br.y);
    ctx.beginPath(); ctx.moveTo(s1.sx, s1.sy); ctx.lineTo(s2.sx, s2.sy); ctx.stroke();
  }
  for(let y = Math.floor(br.y / step) * step; y <= tl.y; y += step) {
    const s1 = worldToScreen(tl.x, y);
    const s2 = worldToScreen(br.x, y);
    ctx.beginPath(); ctx.moveTo(s1.sx, s1.sy); ctx.lineTo(s2.sx, s2.sy); ctx.stroke();
  }
}

function drawConnections() {
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 0.8;
  for(const z of zones) {
    if(!z.id || !z.connections) continue;
    const s1 = worldToScreen(z.x, z.y);
    for(const cid of z.connections) {
      const z2 = zoneMap[cid];
      if(!z2) continue;
      const s2 = worldToScreen(z2.x, z2.y);
      ctx.beginPath(); ctx.moveTo(s1.sx, s1.sy); ctx.lineTo(s2.sx, s2.sy); ctx.stroke();
    }
  }
}

function getPvpColor(z) {
  const pvp = z.pvp_type;
  return PVP_COLORS[pvp] || '#666';
}

function drawZoneMarkers() {
  for(const z of zones) {
    if(z.id === undefined || z.x === undefined) continue;
    const s = worldToScreen(z.x, z.y);
    const col = getPvpColor(z);
    ctx.beginPath();
    ctx.arc(s.sx, s.sy, ZONE_MARKER_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = col;
    ctx.globalAlpha = 0.7;
    ctx.fill();
    ctx.globalAlpha = 1;
  }
}

function drawStartEnd() {
  if(selectedStart) {
    const s = worldToScreen(selectedStart.x, selectedStart.y);
    // Green star
    ctx.beginPath();
    ctx.arc(s.sx, s.sy, 10, 0, Math.PI * 2);
    ctx.fillStyle = '#4caf50';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('A', s.sx, s.sy);
  }
  if(selectedEnd) {
    const s = worldToScreen(selectedEnd.x, selectedEnd.y);
    ctx.beginPath();
    ctx.arc(s.sx, s.sy, 10, 0, Math.PI * 2);
    ctx.fillStyle = '#ff5722';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('B', s.sx, s.sy);
  }
}

function drawRoutePath() {
  if(!currentRoute || currentRoute.path.length < 2) return;
  const path = currentRoute.path;
  // Draw route line
  ctx.strokeStyle = '#00e676';
  ctx.lineWidth = ROUTE_LINE_WIDTH;
  ctx.setLineDash([]);
  ctx.beginPath();
  for(let i = 0; i < path.length; i++) {
    const z = zoneMap[path[i]];
    if(!z || z.x === undefined) continue;
    const s = worldToScreen(z.x, z.y);
    if(i === 0) ctx.moveTo(s.sx, s.sy);
    else ctx.lineTo(s.sx, s.sy);
  }
  ctx.stroke();
  // Draw route nodes
  for(let i = 0; i < path.length; i++) {
    const z = zoneMap[path[i]];
    if(!z || z.x === undefined) continue;
    const s = worldToScreen(z.x, z.y);
    ctx.beginPath();
    ctx.arc(s.sx, s.sy, 3, 0, Math.PI * 2);
    ctx.fillStyle = '#00e676';
    ctx.fill();
  }
}

function drawHoverLabel() {
  if(!hoveredZone) return;
  const s = worldToScreen(hoveredZone.x, hoveredZone.y);
  const name = hoveredZone.name || hoveredZone.file || 'Zone ' + hoveredZone.id;
  ctx.font = '11px sans-serif';
  const metrics = ctx.measureText(name);
  const w = metrics.width + 12;
  const h = 20;
  const x = s.sx - w / 2;
  const y = s.sy - ZONE_MARKER_RADIUS - 28;
  ctx.fillStyle = 'rgba(0,0,0,0.8)';
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = '#fff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(name, s.sx, y + h / 2);
}

function findNearestZone(wx, wy) {
  let best = null, bestDist = Infinity;
  for(const z of zones) {
    if(z.x === undefined || z.y === undefined) continue;
    const d = Math.sqrt((z.x - wx) ** 2 + (z.y - wy) ** 2);
    const screenDist = d * scale;
    if(screenDist < 40 && screenDist < bestDist) {
      best = z;
      bestDist = screenDist;
    }
  }
  return best;
}

function setupEventListeners() {
  canvas.addEventListener('mousedown', e => {
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    oldOffsetX = offsetX;
    oldOffsetY = offsetY;
    canvas.style.cursor = 'grabbing';
  });
  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    if(isDragging) {
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      offsetX = oldOffsetX + dx;
      offsetY = oldOffsetY + dy;
      document.getElementById('statusText').textContent = 'Pan';
    } else {
      const w = screenToWorld(mx, my);
      const z = findNearestZone(w.x, w.y);
      hoveredZone = z;
      if(z) {
        document.getElementById('statusText').textContent = z.name || z.file || 'Zone ' + z.id;
      } else {
        document.getElementById('statusText').textContent = 'Click to set start/end | Scroll to zoom | Drag to pan';
      }
    }
    render();
  });
  canvas.addEventListener('mouseup', e => {
    const dx = Math.abs(e.clientX - dragStartX);
    const dy = Math.abs(e.clientY - dragStartY);
    isDragging = false;
    canvas.style.cursor = 'crosshair';
    if(dx < 5 && dy < 5) {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const w = screenToWorld(mx, my);
      const z = findNearestZone(w.x, w.y);
      if(z) handleClick(z);
    }
    document.getElementById('statusText').textContent = 'Click to set start/end | Scroll to zoom | Drag to pan';
  });
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const oldScale = scale;
    if(e.deltaY < 0) scale *= 1.3;
    else scale /= 1.3;
    scale = Math.max(0.05, Math.min(scale, 50));
    offsetX = mx - (mx - offsetX) * (scale / oldScale);
    offsetY = my - (my - offsetY) * (scale / oldScale);
    render();
  }, {passive: false});
}

function handleClick(z) {
  if(selectedStart && selectedEnd) {
    selectedStart = z;
    selectedEnd = null;
    currentRoute = null;
  } else if(selectedStart) {
    selectedEnd = z;
    currentRoute = null;
  } else {
    selectedStart = z;
    selectedEnd = null;
    currentRoute = null;
  }
  updateUI();
  render();
}

function updateUI() {
  document.getElementById('startName').textContent = selectedStart ? (selectedStart.name || selectedStart.file || 'Zone ' + selectedStart.id) : 'Click on map';
  document.getElementById('endName').textContent = selectedEnd ? (selectedEnd.name || selectedEnd.file || 'Zone ' + selectedEnd.id) : 'Click on map';
}

function clearRoute() {
  selectedStart = null;
  selectedEnd = null;
  currentRoute = null;
  updateUI();
  document.getElementById('routeSummary').style.display = 'none';
  document.getElementById('noRouteMsg').style.display = 'block';
  render();
}

function setupWeights() {
  for(const id of ['weightBlue','weightYellow','weightRed','weightBlack','weightHighway']) {
    const el = document.getElementById(id);
    const valEl = document.getElementById(id.replace('weight','val'));
    el.addEventListener('input', () => { valEl.textContent = el.value; });
  }
}

function setupSearch() {
  const input = document.getElementById('zoneSearch');
  input.addEventListener('input', () => {
    const query = input.value.toLowerCase().trim();
    const results = document.getElementById('searchResults');
    if(!query) { results.innerHTML = ''; return; }
    const matches = zones.filter(z => {
      const name = (z.name || z.file || '').toLowerCase();
      return name.includes(query);
    }).slice(0, 50);
    results.innerHTML = matches.map(z => {
      const pvp = z.pvp_type;
      const badgeClass = pvp ? 'pvp-' + pvp.replace('zone_','') : 'pvp-black';
      return '<div class="search-item" onclick="focusZone('+z.id+')"><span>'+(z.name||z.file||'Zone ')+'</span><span class="pvp-badge '+badgeClass+'">'+pvp+'</span></div>';
    }).join('');
  });
}

function focusZone(id) {
  const z = zoneMap[id];
  if(!z) return;
  const s = worldToScreen(z.x, z.y);
  offsetX = canvas.width / 2 - s.sx + offsetX;
  offsetY = canvas.height / 2 - s.sy + offsetY;
  scale = Math.max(scale, 2);
  render();
}

function dijkstra(startId, endId) {
  const dist = {};
  const prev = {};
  const weightedDist = {};
  const queue = new Set();
  const weights = {
    blue: parseFloat(document.getElementById('weightBlue').value),
    yellow: parseFloat(document.getElementById('weightYellow').value),
    red: parseFloat(document.getElementById('weightRed').value),
    black: parseFloat(document.getElementById('weightBlack').value),
    highway: parseFloat(document.getElementById('weightHighway').value)
  };
  for(const z of zones) {
    if(z.id === undefined) continue;
    dist[z.id] = Infinity;
    weightedDist[z.id] = Infinity;
    prev[z.id] = null;
    queue.add(z.id);
  }
  dist[startId] = 0;
  weightedDist[startId] = 0;

  while(queue.size > 0) {
    let u = null, uWd = Infinity;
    for(const id of queue) {
      if(weightedDist[id] < uWd) { uWd = weightedDist[id]; u = id; }
    }
    if(u === null || uWd === Infinity) break;
    if(u === endId) break;
    queue.delete(u);
    const zu = zoneMap[u];
    if(!zu || !zu.connections) continue;
    for(const v of zu.connections) {
      if(!queue.has(v)) continue;
      const zv = zoneMap[v];
      if(!zv) continue;
      const euclidDist = Math.sqrt((zu.x - zv.x)**2 + (zu.y - zv.y)**2);
      const pvp = zv.pvp_type || '';
      const w = weights[pvp] || weights[pvp.replace('zone_','')] || 5;
      const newDist = dist[u] + euclidDist;
      const newWeighted = weightedDist[u] + euclidDist * w;
      if(newDist < dist[v]) {
        dist[v] = newDist;
        weightedDist[v] = newWeighted;
        prev[v] = u;
      }
    }
  }

  // Reconstruct path
  const path = [];
  let curr = endId;
  while(curr !== null) {
    path.push(curr);
    if(curr === startId) break;
    curr = prev[curr];
  }
  path.reverse();

  if(path[0] !== startId) return null; // no path found

  // Calculate zone breakdown
  const breakdown = {};
  for(const id of path) {
    const z = zoneMap[id];
    if(!z) continue;
    const pvp = z.pvp_type || 'unknown';
    breakdown[pvp] = (breakdown[pvp] || 0) + 1;
  }

  return {
    path,
    distance: dist[endId],
    weightedCost: weightedDist[endId],
    zoneCount: path.length,
    breakdown
  };
}

function calculatePath() {
  if(!selectedStart || !selectedEnd) {
    alert('Please select both start and end zones on the map.');
    return;
  }
  const startId = selectedStart.id;
  const endId = selectedEnd.id;
  if(startId === endId) { alert('Start and end cannot be the same.'); return; }
  currentRoute = dijkstra(startId, endId);
  if(!currentRoute) {
    alert('No path found between these zones.');
    return;
  }
  // Update summary
  document.getElementById('routeSummary').style.display = 'block';
  document.getElementById('noRouteMsg').style.display = 'none';
  document.getElementById('sumDistance').textContent = Math.round(currentRoute.distance);
  document.getElementById('sumZones').textContent = currentRoute.zoneCount;
  const estTimeMin = Math.ceil(currentRoute.zoneCount * 1.5);
  document.getElementById('sumTime').textContent = estTimeMin >= 60 ? (estTimeMin/60).toFixed(1)+'h' : estTimeMin+'m';
  document.getElementById('sumWeighted').textContent = Math.round(currentRoute.weightedCost);

  // Zone breakdown
  const bd = currentRoute.breakdown;
  const total = currentRoute.zoneCount;
  const barEl = document.getElementById('zoneBar');
  const legendEl = document.getElementById('barLegend');
  const textEl = document.getElementById('breakdownText');
  let barHtml = '', legendHtml = '', textHtml = '';
  for(const [pvp, count] of Object.entries(bd)) {
    const pct = Math.round((count / total) * 100);
    const cls = pvp.replace('zone_','');
    barHtml += '<div class="zone-bar-segment '+cls+'" style="width:'+pct+'%">'+pct+'%</div>';
    legendHtml += '<div class="zone-bar-legend-item"><div class="zone-bar-legend-color '+cls+'"></div>'+pvp.split('_').pop()+': '+count+'</div>';
    textHtml += '<span style="color:'+(PVP_COLORS[cls]||'#666')+'">'+pvp+': '+count+' zones</span><br>';
  }
  barEl.innerHTML = barHtml;
  legendEl.innerHTML = legendHtml;
  textEl.innerHTML = textHtml;

  // Path steps
  const stepsEl = document.getElementById('pathSteps');
  let stepsHtml = '';
  for(let i = 0; i < currentRoute.path.length; i++) {
    const id = currentRoute.path[i];
    const z = zoneMap[id];
    if(!z) continue;
    const pvp = z.pvp_type || 'unknown';
    const cls = pvp.replace('zone_','');
    const col = PVP_COLORS[cls] || '#666';
    stepsHtml += '<div class="path-step"><span class="path-step-name">'+(i+1)+'. '+(z.name||z.file||'Zone ')+'</span><span class="path-step-badge pvp-'+cls+'" style="background:'+col+';color:'+(cls==='yellow'?'#000':'#fff')+'">'+cls+'</span></div>';
  }
  stepsEl.innerHTML = stepsHtml;
  render();
}

init();
</script>
</body>
</html>'''

from pathlib import Path
Path(__file__).parent / 'index.html').write_text(html_content)
print('Generated index.html')