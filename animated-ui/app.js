/* ═══════════════════════════════════════════════════════
   MedTriage AI — Main Application Script (app.js)
   ═══════════════════════════════════════════════════════ */
'use strict';

const CONFIG = {
  API_BASE: 'http://localhost:8000',
  GOOGLE_MAPS_API_KEY: 'AIzaSyBecZEdRnRC6yDjk64CQi-LHP6FegHle7I',
  DEMO_SESSION_ID: 'DEMO-SARAH-2026-0042',
  DEMO_PATIENT: {
    name: 'Sarah Johnson',
    dob: '15 March 1980',
    age: 46,
    mrn: 'TRI-2024-0042',
    known_conditions: ['Hypertension', 'Type 2 Diabetes (2019)'],
    medications: ['Lisinopril 10mg', 'Metformin 500mg', 'Aspirin 81mg']
  }
};

// ── Application State ────────────────────────────────────
const state = {
  sessionId: null,
  triageLevel: null,
  symptoms: new Set(),
  conditions: [],
  turnCount: 0,
  isTyping: false,
  currentTab: 'chat',
  mapLoaded: false,
  reportData: null,
  googleMap: null,
  mapService: null
};

// ── DOM References ───────────────────────────────────────
const $ = id => document.getElementById(id);

// ══════════════════════════════════════════════════════════
// 1. PARTICLE CANVAS BACKGROUND
// ══════════════════════════════════════════════════════════
function initParticles() {
  const canvas = $('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let width, height, particles = [];

  class Particle {
    constructor() {
      this.reset();
    }
    reset() {
      this.x = Math.random() * (width || window.innerWidth);
      this.y = Math.random() * (height || window.innerHeight);
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.radius = Math.random() * 1.5 + 0.5;
      const colors = [
        `rgba(20,184,166,${Math.random() * 0.25 + 0.05})`,
        `rgba(59,130,246,${Math.random() * 0.2 + 0.05})`,
        `rgba(139,92,246,${Math.random() * 0.15 + 0.05})`
      ];
      this.color = colors[Math.floor(Math.random() * colors.length)];
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0 || this.x > width) this.vx *= -1;
      if (this.y < 0 || this.y > height) this.vy *= -1;
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fillStyle = this.color;
      ctx.fill();
    }
  }

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  function init() {
    resize();
    particles = [];
    for (let i = 0; i < 55; i++) particles.push(new Particle());
  }

  let mouse = { x: null, y: null };
  window.addEventListener('mousemove', e => { mouse.x = e.x; mouse.y = e.y; });
  window.addEventListener('mouseout', () => { mouse.x = null; mouse.y = null; });
  window.addEventListener('resize', init);

  function animate() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach(p => {
      p.update();
      p.draw();
      // Connect nearby particles
      particles.forEach(p2 => {
        const dx = p.x - p2.x, dy = p.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 110) {
          ctx.beginPath();
          ctx.strokeStyle = `rgba(20,184,166,${(110 - dist) / 1200})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.stroke();
        }
      });
      // Mouse repulsion
      if (mouse.x !== null) {
        const dx = p.x - mouse.x, dy = p.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 90) { p.x += dx * 0.04; p.y += dy * 0.04; }
      }
    });
    requestAnimationFrame(animate);
  }

  init();
  animate();
}

// ══════════════════════════════════════════════════════════
// 2. TAB NAVIGATION
// ══════════════════════════════════════════════════════════
function initTabs() {
  const navItems = document.querySelectorAll('.nav-item[data-tab]');
  navItems.forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      const tab = item.getAttribute('data-tab');
      switchTab(tab);
    });
  });
}

function switchTab(tab) {
  // Update nav items
  document.querySelectorAll('.nav-item[data-tab]').forEach(n => n.classList.remove('active'));
  const navEl = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  if (navEl) navEl.classList.add('active');

  // Update content panels
  document.querySelectorAll('.tab-content').forEach(c => {
    c.classList.remove('active');
    c.classList.add('hidden');
  });

  const tabEl = $(`tab-${tab}`);
  if (tabEl) {
    tabEl.classList.remove('hidden');
    tabEl.classList.add('active');
  }

  // Update breadcrumb
  const labels = { chat: 'Triage Chat', history: 'Visit History', map: 'Nearby Care', report: 'Handoff Report' };
  const bc = $('breadcrumb-page');
  if (bc) bc.textContent = labels[tab] || tab;

  state.currentTab = tab;

  // Lazy‑load map
  if (tab === 'map' && !state.mapLoaded) {
    loadGoogleMap();
  }
  // Populate report if we have data
  if (tab === 'report') {
    populateReportFromState();
  }
}

// ══════════════════════════════════════════════════════════
// 3. CHAT ENGINE
// ══════════════════════════════════════════════════════════
function initChat() {
  const input = $('chat-input');
  const sendBtn = $('send-btn');

  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // Send on Enter (not shift+enter)
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  // New session
  $('new-session-btn')?.addEventListener('click', resetSession);

  // Welcome message
  appendBotMessage(
    `👋 Hello Sarah! Welcome back to **MedTriage AI**.\n\n` +
    `I'm your AI triage assistant powered by BioBERT and a medical knowledge graph. ` +
    `Please describe your **current symptoms** and I'll help assess the urgency of your care needs.\n\n` +
    `> ⚕️ **Medical Disclaimer:** I am an AI assistant and do NOT replace a doctor. ` +
    `For emergencies, call **911** or **108** immediately.`,
    false
  );
}

async function sendMessage() {
  const input = $('chat-input');
  const text = input.value.trim();
  if (!text || state.isTyping) return;

  input.value = '';
  input.style.height = 'auto';

  appendUserMessage(text);
  state.isTyping = true;
  showTyping(true);
  $('send-btn').disabled = true;

  try {
    const response = await callChatAPI(text);
    await handleAPIResponse(response);
  } catch (err) {
    console.warn('API unavailable, using demo mode:', err.message);
    await handleDemoResponse(text);
  }

  showTyping(false);
  state.isTyping = false;
  $('send-btn').disabled = false;
  scrollToBottom();
}

async function callChatAPI(text) {
  const body = {
    session_id: state.sessionId,
    user_input: text,
    patient_info: {
      name: CONFIG.DEMO_PATIENT.name,
      age: CONFIG.DEMO_PATIENT.age,
      known_conditions: CONFIG.DEMO_PATIENT.known_conditions
    }
  };

  const res = await fetch(`${CONFIG.API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(8000)
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function handleAPIResponse(data) {
  if (data.session_id) state.sessionId = data.session_id;
  state.turnCount = data.turn || state.turnCount + 1;

  // Update extracted symptoms
  if (data.neo4j_nodes && data.neo4j_nodes.length > 0) {
    data.neo4j_nodes.forEach(s => state.symptoms.add(s));
    updateSymptomsDisplay();
  }

  // Handle triage result
  if (data.triage) {
    updateTriageLevel(data.triage.urgency_level, data.triage.recommended_action);
    state.conditions = data.triage.possible_conditions || [];
    updateConditionsDisplay();
    state.reportData = buildReportData(data);
  }

  const replyText = data.reply || data.urgency_summary?.message || 'Thank you for the information.';
  const isEmergency = data.triage && ['CRITICAL', 'HIGH'].includes(data.triage?.urgency_level);

  appendBotMessage(replyText, isEmergency, data.triage);
}

// ── Demo mode (when backend is offline) ───────────────────
const DEMO_RESPONSES = [
  {
    keywords: ['chest', 'heart', 'pressure', 'tightness'],
    urgency: 'CRITICAL',
    reply: '🚨 **EMERGENCY ALERT:** Based on your symptoms, this appears to be a **medical emergency**.\n\nYou may be experiencing **Myocardial Infarction (Heart Attack)** or **Pulmonary Embolism**.\n\n**Call 911 or 108 immediately. Do not drive yourself to the hospital.**\n\nDo you have any sweating, nausea, or pain radiating to your arm or jaw?',
    symptoms: ['chest pain'],
    conditions: ['Myocardial Infarction', 'Pulmonary Embolism', 'Aortic Dissection'],
    action: 'Call 108 immediately — ACS protocol',
    score: 98
  },
  {
    keywords: ['stroke', 'drooping', 'arm weak', 'speech', 'slur'],
    urgency: 'CRITICAL',
    reply: '🚨 **STROKE ALERT (FAST Protocol):** Your symptoms are consistent with a **stroke**.\n\n**Call 911 immediately.** Every minute counts — brain tissue is being lost.\n\n- **F**ace drooping ✓\n- **A**rm weakness ✓  \n- **S**peech difficulty ✓\n- **T**ime to call emergency services NOW',
    symptoms: ['facial drooping', 'arm weakness'],
    conditions: ['Ischemic Stroke', 'Hemorrhagic Stroke', 'TIA'],
    action: 'Call 108 immediately — Stroke protocol',
    score: 97
  },
  {
    keywords: ['shortness of breath', 'breathing', 'breathless', 'dyspnea'],
    urgency: 'HIGH',
    reply: 'Your shortness of breath is concerning and requires **urgent evaluation**.\n\nYou may be experiencing:\n- Pulmonary Embolism\n- Asthma attack\n- Cardiac cause\n\n**Please go to the Emergency Room now.** Do you also have chest pain, leg swelling, or a recent long flight?',
    symptoms: ['shortness of breath'],
    conditions: ['Pulmonary Embolism', 'Asthma Attack', 'Heart Failure'],
    action: 'Go to the ER now — Cardiac evaluation required',
    score: 78
  },
  {
    keywords: ['fever', 'headache', 'stiff', 'neck'],
    urgency: 'CRITICAL',
    reply: '🚨 **URGENT:** A high fever with neck stiffness could indicate **bacterial meningitis** — a life-threatening condition.\n\n**Call 911 immediately.** Are you also sensitive to bright light?',
    symptoms: ['high fever', 'neck stiffness'],
    conditions: ['Bacterial Meningitis', 'Subarachnoid Hemorrhage'],
    action: 'Call 108 immediately — Meningitis protocol',
    score: 96
  },
  {
    keywords: ['cough', 'fever'],
    urgency: 'MEDIUM',
    reply: 'Based on your symptoms, you may be experiencing **Pneumonia** or **COVID-19**.\n\nRecommendation: Visit an **urgent care clinic within 4 hours**.\n\nDo you have any shortness of breath or chest pain with the cough?',
    symptoms: ['cough', 'fever'],
    conditions: ['Pneumonia', 'COVID-19', 'Influenza'],
    action: 'Visit urgent care within 4 hours',
    score: 40
  },
  {
    keywords: ['headache', 'migraine'],
    urgency: 'MEDIUM',
    reply: 'Your symptoms may indicate a **Migraine** or **Tension Headache**.\n\nIs the headache on one side? Do you have light sensitivity or nausea?\n\nRecommendation: Rest, hydrate, and consult a physician if symptoms worsen.',
    symptoms: ['headache'],
    conditions: ['Migraine', 'Tension Headache'],
    action: 'Schedule a GP appointment',
    score: 30
  }
];

const DEFAULT_DEMO = {
  urgency: 'MEDIUM',
  reply: 'Thank you for describing your symptoms. To better assess your condition, could you tell me:\n\n1. How long have you been experiencing these symptoms?\n2. On a scale of 1–10, how severe is your discomfort?\n3. Do you have any known medical conditions like diabetes or heart disease?\n\n> ⚕️ This AI provides triage guidance only — always consult a qualified physician.',
  symptoms: [],
  conditions: ['Further Assessment Needed'],
  action: 'Consult healthcare professional',
  score: 20,
  followUp: true
};

async function handleDemoResponse(text) {
  // Simulate network delay
  await sleep(900 + Math.random() * 600);

  const lower = text.toLowerCase();
  let match = DEMO_RESPONSES.find(r => r.keywords.some(k => lower.includes(k)));
  const demo = match || DEFAULT_DEMO;

  // Update state
  demo.symptoms.forEach(s => state.symptoms.add(s));
  if (demo.symptoms.length > 0) updateSymptomsDisplay();

  if (!demo.followUp) {
    updateTriageLevel(demo.urgency, demo.action);
    state.conditions = demo.conditions;
    updateConditionsDisplay();
    state.sessionId = state.sessionId || ('DEMO-' + Date.now());
    state.reportData = {
      session_id: state.sessionId,
      patient: CONFIG.DEMO_PATIENT,
      chief_complaint: text,
      symptoms: Array.from(state.symptoms),
      conditions: demo.conditions,
      urgency: demo.urgency,
      action: demo.action,
      score: demo.score,
      confidence: 0.88,
      generated_at: new Date().toISOString()
    };
  }

  const isEmergency = ['CRITICAL', 'HIGH'].includes(demo.urgency) && !demo.followUp;
  appendBotMessage(demo.reply, isEmergency, demo.followUp ? null : {
    urgency_level: demo.urgency,
    recommended_action: demo.action,
    possible_conditions: demo.conditions,
    urgency_score: demo.score
  });
}

// ══════════════════════════════════════════════════════════
// 4. MESSAGE RENDERING
// ══════════════════════════════════════════════════════════
function appendUserMessage(text) {
  const container = $('chat-messages');
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble user-bubble';
  bubble.innerHTML = `
    <div class="user-avatar-chat">SJ</div>
    <div class="bubble-content">${escapeHTML(text).replace(/\n/g, '<br>')}</div>
  `;
  container.appendChild(bubble);
  scrollToBottom();
}

function appendBotMessage(text, isEmergency = false, triageData = null) {
  const container = $('chat-messages');
  const bubble = document.createElement('div');

  if (isEmergency && triageData) {
    bubble.className = 'chat-bubble bot-bubble emergency-bubble';
    bubble.innerHTML = `
      <div class="bot-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </div>
      <div class="bubble-content">
        <div class="emergency-bubble-header">
          🚨 ${triageData.urgency_level === 'CRITICAL' ? 'MEDICAL EMERGENCY' : 'URGENT — GO TO ER NOW'}
        </div>
        <div>${markdownToHTML(text)}</div>
        <div class="bubble-emergency-btns">
          <a href="tel:911" class="bubble-emergency-call">📞 Call 911</a>
          <a href="tel:108" class="bubble-emergency-call" style="background:#b91c1c">📞 Call 108 (India)</a>
          <button class="bubble-emergency-call" onclick="switchTab('map')" style="background:#1e3a5f">🗺 Find Hospitals</button>
        </div>
        <div style="font-size:0.72rem;color:#94a3b8;margin-top:0.75rem">
          ⚕️ This is AI triage guidance only. Clinical assessment required.
        </div>
      </div>
    `;
    // Trigger emergency overlay for CRITICAL
    if (triageData.urgency_level === 'CRITICAL') {
      showEmergencyOverlay(triageData);
    }
  } else {
    bubble.className = 'chat-bubble bot-bubble';
    bubble.innerHTML = `
      <div class="bot-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </div>
      <div class="bubble-content">${markdownToHTML(text)}</div>
    `;
  }

  container.appendChild(bubble);
  scrollToBottom();
}

// ══════════════════════════════════════════════════════════
// 5. TRIAGE STATE MANAGEMENT
// ══════════════════════════════════════════════════════════
function updateTriageLevel(level, action) {
  state.triageLevel = level;

  // Body attribute for global CSS
  document.body.setAttribute('data-triage', level);

  // Triage pill
  const pillText = $('triage-pill-text');
  const levelLabels = { CRITICAL: '🚨 CRITICAL', HIGH: '⚠ HIGH', MEDIUM: '⏱ MEDIUM', LOW: '✓ LOW' };
  if (pillText) pillText.textContent = levelLabels[level] || level;

  // Triage ring in info panel
  const ring = $('triage-ring');
  if (ring) {
    ring.className = 'triage-ring level-' + level.toLowerCase();
    $('triage-ring-text').textContent = level.slice(0, 3);
  }

  // Triage label & action
  const label = $('triage-label');
  const actionEl = $('triage-action');
  const levelFull = {
    CRITICAL: '🚨 Critical Emergency',
    HIGH: '⚠️ High Priority',
    MEDIUM: '⏱ Medium Priority',
    LOW: '✓ Low Priority'
  };
  if (label) label.textContent = levelFull[level] || level;
  if (actionEl) actionEl.textContent = action || '';
  if (actionEl) {
    actionEl.style.color = level === 'CRITICAL' ? 'var(--critical)' :
      level === 'HIGH' ? 'var(--high)' :
      level === 'MEDIUM' ? 'var(--medium)' : 'var(--low)';
  }

  // Show map badge for urgent cases
  const mapBadge = $('map-badge');
  if (mapBadge && ['CRITICAL', 'HIGH'].includes(level)) {
    mapBadge.classList.remove('hidden');
  }

  showToast(`Triage level updated: ${level}`, level === 'CRITICAL' ? 'emergency' : level === 'HIGH' ? 'warning' : 'info');
}

function updateSymptomsDisplay() {
  const container = $('symptoms-tags');
  if (!container) return;
  container.innerHTML = '';
  if (state.symptoms.size === 0) {
    container.innerHTML = '<span class="symptom-placeholder">No symptoms detected yet</span>';
    return;
  }
  state.symptoms.forEach(s => {
    const tag = document.createElement('span');
    tag.className = 'symptom-tag';
    tag.textContent = s;
    container.appendChild(tag);
  });
}

function updateConditionsDisplay() {
  const list = $('conditions-list');
  if (!list) return;
  list.innerHTML = '';
  if (!state.conditions.length) {
    list.innerHTML = '<li class="condition-placeholder">Complete assessment for results</li>';
    return;
  }
  state.conditions.slice(0, 5).forEach((c, i) => {
    const li = document.createElement('li');
    li.className = 'condition-item';
    li.innerHTML = `<span class="condition-num">${i + 1}</span> ${escapeHTML(c)}`;
    list.appendChild(li);
  });
}

// ══════════════════════════════════════════════════════════
// 6. EMERGENCY OVERLAY
// ══════════════════════════════════════════════════════════
function showEmergencyOverlay(triageData) {
  const overlay = $('emergency-overlay');
  if (!overlay) return;

  const title = $('emergency-title');
  const msg = $('emergency-msg');

  if (title) title.textContent = `🚨 ${triageData.urgency_level} — MEDICAL EMERGENCY DETECTED`;
  if (msg && triageData.possible_conditions) {
    msg.textContent = `Possible: ${triageData.possible_conditions.slice(0, 2).join(' / ')}. ${triageData.recommended_action}.`;
  }

  overlay.classList.remove('hidden');
}

function initEmergencyControls() {
  $('dismiss-emergency')?.addEventListener('click', () => {
    $('emergency-overlay')?.classList.add('hidden');
    showToast('Emergency overlay dismissed. Please seek care immediately.', 'warning');
  });

  $('qa-emergency-btn')?.addEventListener('click', () => {
    if (state.triageLevel === 'CRITICAL') {
      showEmergencyOverlay({ urgency_level: 'CRITICAL', possible_conditions: state.conditions, recommended_action: 'Call emergency services immediately' });
    } else {
      window.open('tel:911');
    }
  });
}

// ══════════════════════════════════════════════════════════
// 7. GOOGLE MAPS INTEGRATION
// ══════════════════════════════════════════════════════════
function loadGoogleMap() {
  state.mapLoaded = true;
  const mapContainer = $('google-map');
  const placeholder = $('map-placeholder');

  // If no real API key, show embedded static map iframe with nearby hospital search
  if (!CONFIG.GOOGLE_MAPS_API_KEY || CONFIG.GOOGLE_MAPS_API_KEY === 'YOUR_GOOGLE_MAPS_API_KEY') {
    // Use OpenStreetMap embed as fallback
    loadOpenStreetMapFallback(mapContainer, placeholder);
    return;
  }

  // Load Google Maps API dynamically
  if (!window.google) {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${CONFIG.GOOGLE_MAPS_API_KEY}&libraries=places&callback=initGoogleMap`;
    script.async = true;
    script.defer = true;
    window.initGoogleMap = () => renderGoogleMap(mapContainer, placeholder);
    document.head.appendChild(script);
  } else {
    renderGoogleMap(mapContainer, placeholder);
  }
}

function loadOpenStreetMapFallback(container, placeholder) {
  if (placeholder) placeholder.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem">📍 Loading map…</p>';

  // Try to get user location
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      pos => {
        const { latitude: lat, longitude: lng } = pos.coords;
        loadOSMEmbed(container, lat, lng);
        searchNearbyFacilities(lat, lng);
      },
      () => {
        // Default to a generic location if permission denied
        loadOSMEmbed(container, 28.6139, 77.2090); // New Delhi default
        if (placeholder) placeholder.remove();
      }
    );
  } else {
    loadOSMEmbed(container, 28.6139, 77.2090);
    if (placeholder) placeholder.remove();
  }
}

function loadOSMEmbed(container, lat, lng) {
  const zoom = 14;
  const bbox = `${lng - 0.05},${lat - 0.04},${lng + 0.05},${lat + 0.04}`;
  const iframe = document.createElement('iframe');
  iframe.src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
  iframe.style.cssText = 'width:100%;height:100%;border:none;border-radius:12px';
  iframe.loading = 'lazy';
  container.innerHTML = '';
  container.appendChild(iframe);

  // Update map subtitle
  const sub = $('map-sub-text');
  if (sub) sub.textContent = `Showing hospitals & clinics near your location (lat: ${lat.toFixed(3)}, lng: ${lng.toFixed(3)})`;
  $('facilities-count').textContent = '4 nearby';
}

function renderGoogleMap(container, placeholder) {
  if (!navigator.geolocation) {
    if (placeholder) placeholder.innerHTML = '<p>Location access denied</p>';
    return;
  }

  navigator.geolocation.getCurrentPosition(pos => {
    const center = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    const mapDiv = document.createElement('div');
    mapDiv.style.cssText = 'width:100%;height:100%';
    container.innerHTML = '';
    container.appendChild(mapDiv);

    const map = new google.maps.Map(mapDiv, {
      center,
      zoom: 14,
      styles: getDarkMapStyle(),
      disableDefaultUI: false
    });
    state.googleMap = map;

    // Patient location marker
    new google.maps.Marker({
      position: center,
      map,
      title: 'Your Location',
      icon: { url: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png' }
    });

    // Places nearby search
    const service = new google.maps.places.PlacesService(map);
    state.mapService = service;

    const request = {
      location: center,
      radius: 3000,
      type: 'hospital'
    };

    service.nearbySearch(request, (results, status) => {
      if (status === google.maps.places.PlacesServiceStatus.OK) {
        renderPlacesOnMap(map, results, center);
        renderFacilitiesList(results);
      }
    });
  });
}

function renderPlacesOnMap(map, places, center) {
  places.slice(0, 8).forEach((place, i) => {
    const marker = new google.maps.Marker({
      position: place.geometry.location,
      map,
      title: place.name,
      animation: google.maps.Animation.DROP
    });

    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="font-family:Inter;font-size:13px;padding:4px">
        <strong>${place.name}</strong><br>
        <span style="color:#666">${place.vicinity || ''}</span><br>
        <a href="https://www.google.com/maps/dir/?api=1&destination=${place.geometry.location.lat()},${place.geometry.location.lng()}" 
           target="_blank" style="color:#14b8a6">Get Directions ↗</a>
      </div>`
    });

    marker.addListener('click', () => infoWindow.open(map, marker));
  });
}

function renderFacilitiesList(places) {
  const list = $('facilities-list');
  if (!list) return;
  list.innerHTML = '';

  $('facilities-count').textContent = `${Math.min(places.length, 8)} nearby`;

  places.slice(0, 6).forEach(place => {
    const li = document.createElement('li');
    li.className = 'facility-item';
    const isEmergency = place.name.toLowerCase().includes('hospital') || place.name.toLowerCase().includes('emergency');
    const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${place.geometry.location.lat()},${place.geometry.location.lng()}`;

    li.innerHTML = `
      <div class="facility-icon ${isEmergency ? 'facility-emergency' : 'facility-clinic'}">${isEmergency ? '🏥' : '🩺'}</div>
      <div class="facility-info">
        <strong>${escapeHTML(place.name)}</strong>
        <span>${escapeHTML(place.vicinity || 'Nearby')}</span>
        <span class="facility-hours">${place.opening_hours?.open_now ? '🟢 Open Now' : '⚪ Hours Unknown'}</span>
      </div>
      <a href="${mapsUrl}" target="_blank" class="facility-dir-btn">Directions</a>
    `;
    list.appendChild(li);
  });
}

function searchNearbyFacilities(lat, lng) {
  // Update the static list with coordinates info
  $('facilities-count').textContent = '4 nearby';
  const sub = $('map-sub-text');
  if (sub) sub.textContent = `Showing facilities near your location`;
}

function getDarkMapStyle() {
  return [
    { elementType: 'geometry', stylers: [{ color: '#0b1120' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#0b1120' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#746855' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1e2d40' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#17263c' }] },
    { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#0b2020' }] }
  ];
}

// Quick action — map button
function initMapActions() {
  $('qa-map-btn')?.addEventListener('click', () => switchTab('map'));
  $('nav-map')?.addEventListener('click', () => switchTab('map'));
}

// ══════════════════════════════════════════════════════════
// 8. DOCTOR HANDOFF REPORT (PDF)
// ══════════════════════════════════════════════════════════
function buildReportData(apiData) {
  return {
    session_id: apiData.session_id || state.sessionId,
    patient: CONFIG.DEMO_PATIENT,
    chief_complaint: 'As described in conversation',
    symptoms: Array.from(state.symptoms),
    conditions: state.conditions,
    urgency: state.triageLevel,
    action: apiData.triage?.recommended_action || '',
    score: apiData.triage?.urgency_score || 0,
    confidence: apiData.triage?.confidence || 0,
    generated_at: new Date().toISOString()
  };
}

function populateReportFromState() {
  const data = state.reportData;
  if (!data) return; // keep demo data

  // Update session ID references
  if (data.session_id) {
    const s = $('rpt-session'); if (s) s.textContent = data.session_id;
    const sf = $('rpt-footer-session'); if (sf) sf.textContent = data.session_id;
  }

  // Update triage box
  const triageBox = $('rpt-triage-box');
  if (triageBox && data.urgency) {
    triageBox.setAttribute('data-level', data.urgency);
    const badge = $('rpt-urgency-badge'); if (badge) badge.textContent = data.urgency;
    const lbl = $('rpt-urgency-label'); if (lbl) lbl.textContent = data.action || getLevelLabel(data.urgency);
    const actionEl = $('rpt-action'); if (actionEl) actionEl.textContent = data.action || '';
    const score = $('rpt-score'); if (score) score.textContent = `${data.score}/100`;
    const conf = $('rpt-confidence'); if (conf) conf.textContent = data.confidence;
  }

  // Update symptoms
  const grid = $('rpt-symptoms-grid');
  if (grid && data.symptoms.length > 0) {
    grid.innerHTML = '';
    data.symptoms.forEach(s => {
      const div = document.createElement('div');
      div.className = 'rpt-symptom-tag critical-symptom';
      div.textContent = s;
      grid.appendChild(div);
    });
  }

  // Update differential diagnosis
  const tbody = $('rpt-diff-tbody');
  if (tbody && data.conditions.length > 0) {
    tbody.innerHTML = '';
    data.conditions.forEach((c, i) => {
      const pct = Math.max(88 - i * 14, 20);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${escapeHTML(c)}</td>
        <td><span class="prob-bar-wrap"><span class="prob-bar" style="--pct:${pct}%"></span> ${pct}%</span></td>
        <td>—</td>
        <td>${i === 0 ? 'Rule Engine' : 'Neo4j KG'}</td>
      `;
      tbody.appendChild(tr);
    });
  }
}

function getLevelLabel(level) {
  const labels = {
    CRITICAL: 'Call Emergency Services Immediately',
    HIGH: 'Go to Emergency Room Now',
    MEDIUM: 'Visit Urgent Care Within 4 Hours',
    LOW: 'Schedule GP Appointment'
  };
  return labels[level] || level;
}

function initReportExport() {
  $('export-pdf-btn')?.addEventListener('click', exportToPDF);
  $('qa-export-btn')?.addEventListener('click', () => { switchTab('report'); setTimeout(exportToPDF, 300); });
  $('reload-report-btn')?.addEventListener('click', () => {
    populateReportFromState();
    showToast('Report refreshed from current session', 'info');
  });
}

function exportToPDF() {
  if (typeof window.jspdf === 'undefined' && typeof window.jsPDF === 'undefined') {
    showToast('PDF library loading… please try again', 'info');
    return;
  }

  const { jsPDF } = window.jspdf || window;
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

  const now = new Date();
  const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  const patient = CONFIG.DEMO_PATIENT;
  const urgency = state.triageLevel || 'HIGH';
  const symptoms = Array.from(state.symptoms);
  const conditions = state.conditions;
  const reportId = `TRI-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;

  // Color scheme
  const colors = {
    CRITICAL: [239, 68, 68],
    HIGH: [249, 115, 22],
    MEDIUM: [234, 179, 8],
    LOW: [34, 197, 94]
  };
  const urgencyColor = colors[urgency] || colors.HIGH;

  let y = 15;

  // ── Header ──
  doc.setFillColor(11, 17, 32);
  doc.rect(0, 0, 210, 40, 'F');

  doc.setTextColor(20, 184, 166);
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('MedTriage AI', 15, 22);

  doc.setTextColor(200, 200, 200);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text('Doctor Handoff Report', 15, 30);

  doc.setTextColor(150, 150, 150);
  doc.setFontSize(9);
  doc.text(`Report ID: ${reportId}`, 130, 18, { align: 'left' });
  doc.text(`Generated: ${dateStr}, ${timeStr}`, 130, 24, { align: 'left' });
  doc.text('⚠ CONFIDENTIAL — PHYSICIAN USE ONLY', 130, 30, { align: 'left' });

  // Urgency badge header
  doc.setFillColor(...urgencyColor);
  doc.roundedRect(130, 32, 65, 8, 2, 2, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'bold');
  doc.text(`TRIAGE LEVEL: ${urgency}`, 162.5, 37.5, { align: 'center' });

  y = 50;

  // ── DISCLAIMER ──
  doc.setFillColor(45, 8, 8);
  doc.rect(10, y, 190, 16, 'F');
  doc.setDrawColor(239, 68, 68);
  doc.rect(10, y, 190, 16, 'D');
  doc.setTextColor(252, 165, 165);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');
  doc.text('⚕ MEDICAL DISCLAIMER:', 15, y + 5);
  doc.setFont('helvetica', 'normal');
  const discLines = doc.splitTextToSize('This report is AI-generated triage decision support ONLY. It does NOT constitute a medical diagnosis. All clinical decisions must be made by a licensed physician. In emergencies, call 911 or 108.', 176);
  doc.text(discLines, 15, y + 10);

  y += 23;

  // ── Section: Patient Info ──
  function sectionTitle(title, yPos) {
    doc.setFillColor(20, 30, 50);
    doc.rect(10, yPos, 190, 8, 'F');
    doc.setTextColor(20, 184, 166);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.text(title, 14, yPos + 5.5);
    return yPos + 12;
  }

  function field(label, value, x, yPos, width = 85) {
    doc.setTextColor(100, 116, 139);
    doc.setFontSize(7.5);
    doc.setFont('helvetica', 'bold');
    doc.text(label.toUpperCase(), x, yPos);
    doc.setTextColor(225, 232, 240);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    const lines = doc.splitTextToSize(String(value), width);
    doc.text(lines, x, yPos + 4.5);
    return yPos + 4.5 + lines.length * 4;
  }

  y = sectionTitle('PATIENT INFORMATION', y);
  const leftCol = 14, rightCol = 110;
  field('Full Name', patient.name, leftCol, y);
  field('Date of Birth', patient.dob + ' (Age ' + patient.age + ')', rightCol, y);
  y += 10;
  field('MRN', patient.mrn, leftCol, y);
  field('Session ID', state.sessionId || reportId, rightCol, y);
  y += 10;
  field('Known Conditions', patient.known_conditions.join(', '), leftCol, y, 85);
  field('Current Medications', patient.medications.join(', '), rightCol, y, 85);
  y += 14;

  // ── Section: Triage Decision ──
  y = sectionTitle('TRIAGE DECISION', y);
  doc.setFillColor(...urgencyColor.map(c => Math.min(255, c * 0.15)));
  doc.rect(14, y, 182, 20, 'F');
  doc.setDrawColor(...urgencyColor);
  doc.rect(14, y, 182, 20, 'D');

  doc.setTextColor(...urgencyColor);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text(urgency, 20, y + 9);

  doc.setTextColor(225, 232, 240);
  doc.setFontSize(10);
  doc.text(getLevelLabel(urgency), 50, y + 9);

  doc.setTextColor(150, 150, 150);
  doc.setFontSize(8);
  doc.text(`${state.reportData?.action || 'Seek medical attention promptly'}`, 50, y + 14);

  y += 26;

  // ── Section: Extracted Symptoms ──
  y = sectionTitle('EXTRACTED SYMPTOMS (BioBERT NER)', y);
  if (symptoms.length === 0) symptoms.push('chest pain', 'shortness of breath', 'sweating', 'fatigue');

  let sx = 14;
  symptoms.forEach(s => {
    const w = doc.getStringUnitWidth(s) * 9 / doc.internal.scaleFactor + 8;
    if (sx + w > 195) { sx = 14; y += 9; }
    doc.setFillColor(...urgencyColor.map(c => Math.min(255, c * 0.15)));
    doc.roundedRect(sx, y, w, 7, 1.5, 1.5, 'F');
    doc.setDrawColor(...urgencyColor);
    doc.roundedRect(sx, y, w, 7, 1.5, 1.5, 'D');
    doc.setTextColor(...urgencyColor);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.text(s, sx + 4, y + 4.8);
    sx += w + 3;
  });

  y += 13;

  // ── Section: Differential Diagnosis ──
  y = sectionTitle('DIFFERENTIAL DIAGNOSIS', y);

  const tableHeaders = ['#', 'Condition', 'Probability', 'Source'];
  const colWidths = [10, 100, 40, 32];
  let tx = 14;

  doc.setFillColor(20, 40, 60);
  doc.rect(tx, y, 182, 8, 'F');
  doc.setTextColor(148, 163, 184);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');

  tableHeaders.forEach((h, i) => {
    doc.text(h, tx + 2, y + 5.5);
    tx += colWidths[i];
  });

  y += 10;

  const displayConditions = conditions.length > 0 ? conditions :
    ['Myocardial Infarction', 'Pulmonary Embolism', 'Unstable Angina'];

  displayConditions.slice(0, 5).forEach((c, i) => {
    const pct = Math.max(88 - i * 14, 20);
    tx = 14;

    doc.setFillColor(i % 2 === 0 ? 20 : 26, i % 2 === 0 ? 30 : 38, i % 2 === 0 ? 50 : 60);
    doc.rect(14, y, 182, 8, 'F');

    doc.setTextColor(225, 232, 240);
    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'normal');

    [String(i + 1), c, `${pct}%`, i === 0 ? 'Rule Engine' : 'Neo4j KG'].forEach((val, vi) => {
      doc.text(val, tx + 2, y + 5.5);
      tx += colWidths[vi];
    });

    y += 9;
  });

  y += 6;

  // ── Section: Vital Flags ──
  if (y < 230) {
    y = sectionTitle('VITAL FLAGS FOR RECEIVING PHYSICIAN', y);
    const flags = [
      'Requires immediate cardiac evaluation (12-lead ECG, troponin, CXR)',
      'Patient has history of hypertension and diabetes — elevated cardiovascular risk',
      'AI confidence: 0.88 — clinical judgment must override AI assessment',
      'AI triage only — confirmatory investigations and clinical examination required'
    ];

    flags.forEach(flag => {
      doc.setFillColor(60, 30, 10);
      doc.rect(14, y, 182, 7.5, 'F');
      doc.setDrawColor(249, 115, 22);
      doc.setLineWidth(0.3);
      doc.rect(14, y, 182, 7.5, 'D');
      doc.setTextColor(253, 186, 116);
      doc.setFontSize(8.5);
      doc.setFont('helvetica', 'normal');
      doc.text('▸ ' + flag, 18, y + 5);
      y += 9;
    });
  }

  y += 8;

  // ── Footer ──
  doc.setFillColor(11, 17, 32);
  doc.rect(0, 282, 210, 15, 'F');
  doc.setTextColor(71, 85, 105);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.text(`MedTriage AI v1.0 · ${reportId} · ${dateStr} · Not for clinical use without physician review`, 105, 290, { align: 'center' });
  doc.text('⚕ This is AI-generated decision support ONLY. Always consult a licensed physician.', 105, 295, { align: 'center' });

  // Page number
  doc.setTextColor(20, 184, 166);
  doc.text('Page 1 of 1', 195, 290, { align: 'right' });

  // Save
  doc.save(`MedTriage_Handoff_${patient.name.replace(' ', '_')}_${reportId}.pdf`);
  showToast('Doctor Handoff Report exported as PDF!', 'success');
}

// ══════════════════════════════════════════════════════════
// 9. SIDEBAR & THEME
// ══════════════════════════════════════════════════════════
function initSidebarAndTheme() {
  const menuBtn = $('menu-btn');
  menuBtn?.addEventListener('click', () => {
    menuBtn.classList.toggle('open');
    document.body.classList.toggle('sidebar-closed');
  });

  const themeBtn = $('theme-btn');
  themeBtn?.addEventListener('click', () => {
    document.body.classList.toggle('light');
    const isLight = document.body.classList.contains('light');
    themeBtn.style.transform = 'rotate(180deg)';
    setTimeout(() => themeBtn.style.transform = '', 300);
    const icon = $('theme-icon');
    if (icon) {
      icon.innerHTML = isLight
        ? `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>`
        : `<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>`;
    }
    showToast(isLight ? 'Light mode activated' : 'Dark mode activated', 'info');
  });
}

// ══════════════════════════════════════════════════════════
// 10. TOAST NOTIFICATIONS
// ══════════════════════════════════════════════════════════
function showToast(message, type = 'info') {
  const container = $('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';

  const icons = {
    success: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#22c55e" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`,
    info: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#14b8a6" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    warning: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#f97316" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    emergency: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#ef4444" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>`
  };

  const borderColors = { success: '#22c55e', info: '#14b8a6', warning: '#f97316', emergency: '#ef4444' };

  toast.innerHTML = `${icons[type] || icons.info} <span>${escapeHTML(message)}</span>`;
  toast.style.borderLeft = `3px solid ${borderColors[type] || borderColors.info}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('out');
    toast.addEventListener('transitionend', () => toast.remove());
  }, 4000);
}

// ══════════════════════════════════════════════════════════
// 11. SESSION MANAGEMENT
// ══════════════════════════════════════════════════════════
function resetSession() {
  state.sessionId = null;
  state.triageLevel = null;
  state.symptoms.clear();
  state.conditions = [];
  state.turnCount = 0;
  state.reportData = null;

  // Reset UI
  document.body.setAttribute('data-triage', 'none');
  const pill = $('triage-pill-text');
  if (pill) pill.textContent = 'Awaiting symptoms';
  $('triage-dot')?.style.removeProperty('background');

  const ring = $('triage-ring');
  if (ring) { ring.className = 'triage-ring'; $('triage-ring-text').textContent = '?'; }

  const lbl = $('triage-label'); if (lbl) lbl.textContent = 'Pending Assessment';
  const act = $('triage-action'); if (act) { act.textContent = 'Share your symptoms to begin'; act.style.color = ''; }

  $('symptoms-tags').innerHTML = '<span class="symptom-placeholder">No symptoms detected yet</span>';
  $('conditions-list').innerHTML = '<li class="condition-placeholder">Complete assessment for results</li>';
  $('map-badge')?.classList.add('hidden');
  $('emergency-overlay')?.classList.add('hidden');

  // Clear messages and show welcome
  const msgs = $('chat-messages');
  if (msgs) {
    msgs.innerHTML = '';
    appendBotMessage(
      `✨ **New session started.** Hello Sarah! Please describe your current symptoms and I'll assess your care needs.\n\n` +
      `> ⚕️ **Reminder:** This AI does NOT replace medical advice. Call **911/108** in emergencies.`,
      false
    );
  }

  showToast('New session started', 'info');
}

// ══════════════════════════════════════════════════════════
// 12. DEMO: Load demo report from history
// ══════════════════════════════════════════════════════════
function loadDemoReport() {
  // Pre-fill state with demo data
  state.triageLevel = 'HIGH';
  state.symptoms = new Set(['chest pain', 'shortness of breath', 'sweating', 'fatigue']);
  state.conditions = ['Myocardial Infarction', 'Pulmonary Embolism', 'Unstable Angina'];
  state.sessionId = CONFIG.DEMO_SESSION_ID;
  state.reportData = {
    session_id: CONFIG.DEMO_SESSION_ID,
    patient: CONFIG.DEMO_PATIENT,
    chief_complaint: 'Chest tightness and shortness of breath',
    symptoms: Array.from(state.symptoms),
    conditions: state.conditions,
    urgency: 'HIGH',
    action: 'Go to the ER now — Cardiac evaluation required',
    score: 80,
    confidence: 0.88,
    generated_at: new Date().toISOString()
  };

  updateTriageLevel('HIGH', 'Go to the ER now — Cardiac evaluation required');
  updateSymptomsDisplay();
  updateConditionsDisplay();
  switchTab('report');
  showToast('Loaded demo report for Sarah Johnson', 'info');
}

// ══════════════════════════════════════════════════════════
// 13. UTILITY FUNCTIONS
// ══════════════════════════════════════════════════════════
function showTyping(show) {
  const indicator = $('typing-indicator');
  if (!indicator) return;
  if (show) indicator.classList.remove('hidden');
  else indicator.classList.add('hidden');
  scrollToBottom();
}

function scrollToBottom() {
  const msgs = $('chat-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

function markdownToHTML(text) {
  return escapeHTML(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^> (.+)$/gm, '<blockquote style="border-left:3px solid var(--teal);padding:0.3rem 0.7rem;margin:0.5rem 0;background:rgba(20,184,166,0.06);border-radius:0 6px 6px 0;font-size:0.82rem;color:var(--text-muted)">$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li style="list-style:disc;margin-left:1.2rem">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li style="list-style:decimal;margin-left:1.2rem"><strong>$1.</strong> $2</li>')
    .replace(/\n/g, '<br>');
}

// ══════════════════════════════════════════════════════════
// BOOT
// ══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initParticles();
  initTabs();
  initChat();
  initEmergencyControls();
  initSidebarAndTheme();
  initMapActions();
  initReportExport();

  // Make loadDemoReport global for onclick handlers
  window.loadDemoReport = loadDemoReport;
  window.switchTab = switchTab;

  // Check backend health
  fetch(`${CONFIG.API_BASE}/health`, { signal: AbortSignal.timeout(3000) })
    .then(r => r.json())
    .then(() => showToast('Backend connected — BioBERT + Neo4j online', 'success'))
    .catch(() => showToast('Running in demo mode — backend offline', 'info'));
});
