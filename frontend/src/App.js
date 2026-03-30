import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";

const API = "http://localhost:9000";

// ── Design Tokens (mirrored from Nexus style.css) ──────────────────────────
const T = {
  purple:      "hsl(262, 90%, 66%)",
  purpleDim:   "hsl(262, 80%, 55%)",
  purpleGlow:  "hsl(262, 90%, 66%, 0.35)",
  cyan:        "hsl(185, 90%, 55%)",
  cyanGlow:    "hsl(185, 90%, 55%, 0.3)",
  green:       "hsl(148, 70%, 52%)",
  greenGlow:   "hsl(148, 70%, 52%, 0.3)",
  orange:      "hsl(30, 100%, 60%)",
  orangeGlow:  "hsl(30, 100%, 60%, 0.3)",
  red:         "hsl(0, 90%, 62%)",
  redGlow:     "hsl(0, 90%, 62%, 0.3)",
  bg:          "hsl(228, 28%, 7%)",
  bg2:         "hsl(228, 24%, 10%)",
  surface:     "hsl(228, 22%, 13%)",
  surface2:    "hsl(228, 18%, 18%)",
  border:      "hsl(228, 18%, 22%)",
  borderLight: "hsl(228, 18%, 28%)",
  textPrimary: "hsl(220, 20%, 96%)",
  textSec:     "hsl(220, 12%, 60%)",
  textMuted:   "hsl(220, 10%, 40%)",
  easeSpring:  "cubic-bezier(0.34, 1.56, 0.64, 1)",
  easeOut:     "cubic-bezier(0.16, 1, 0.3, 1)",
};

const URGENCY_CONFIG = {
  CRITICAL: { color: T.red,    glow: T.redGlow,    icon: "🚨", label: "CRITICAL — Call 108",   accent: "hsl(0,90%,62%,0.12)"   },
  HIGH:     { color: T.orange, glow: T.orangeGlow, icon: "⚠️", label: "HIGH — Go to ER Now",   accent: "hsl(30,100%,60%,0.10)"  },
  MEDIUM:   { color: "hsl(50,100%,55%)", glow: "hsl(50,100%,55%,0.3)", icon: "🔶", label: "MEDIUM — Urgent Care", accent: "hsl(50,100%,55%,0.10)" },
  LOW:      { color: T.green,  glow: T.greenGlow,  icon: "✅", label: "LOW — See a Doctor",     accent: "hsl(148,70%,52%,0.10)"  },
};

const SUGGESTIONS = [
  "My head has been throbbing and I feel hot",
  "I have a tight chest and can't breathe",
  "My face is drooping and arm feels weak",
  "I've been dizzy and keep throwing up",
  "Everything hurts, runny nose and coughing",
];

let _id = 0;
const uid = () => ++_id;

// ── Particle Canvas ────────────────────────────────────────────────────────
function ParticleCanvas() {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf, W, H;
    const particles = [];
    const N = 70;

    const resize = () => {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < N; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        r: Math.random() * 1.5 + 0.3,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        alpha: Math.random() * 0.5 + 0.1,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      for (const p of particles) {
        p.x += p.vx;  p.y += p.vy;
        if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
        if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(220, 60%, 80%, ${p.alpha})`;
        ctx.fill();
      }
      // connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `hsla(262, 80%, 70%, ${0.08 * (1 - dist / 100)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  return <canvas ref={ref} style={S.canvas} />;
}

// ── Score Bar ──────────────────────────────────────────────────────────────
function ScoreBar({ score, color }) {
  const [w, setW] = useState(0);
  useEffect(() => { const t = setTimeout(() => setW(score), 100); return () => clearTimeout(t); }, [score]);
  return (
    <div style={S.scoreWrap}>
      <div style={S.scoreTrack}>
        <div style={{
          ...S.scoreFill,
          width: `${w}%`,
          background: color,
          boxShadow: `0 0 12px ${color}88`,
          transition: "width 1.2s " + T.easeOut,
        }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 44 }}>{score}/100</span>
    </div>
  );
}

// ── Bot Response ───────────────────────────────────────────────────────────
function BotResponse({ msg, sessionId }) {
  const { nodes, triage } = msg;
  const cfg = triage ? URGENCY_CONFIG[triage.urgency_level] : null;
  return (
    <div className="msgSlide" style={{ marginBottom: 20 }}>
      
      {/* The LLM Conversational Reply */}
      {msg.text && (
        <div style={{ ...S.botBubbleWrap }} className="revealUp">
          <div style={S.botBubble}>{msg.text}</div>
        </div>
      )}

      {nodes?.length > 0 && (
        <div style={S.card} className="revealUp">
          <div style={S.cardTitle}>🔬 Extracted Symptoms</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {nodes.map((n, i) => (
              <span key={i} className="tagPop" style={{ ...S.tag, animationDelay: `${i * 0.07}s` }}>{n}</span>
            ))}
          </div>
        </div>
      )}

      {nodes?.length === 0 && (
        <div style={S.card} className="revealUp">
          <span style={{ color: T.textMuted, fontSize: 14 }}>
            No symptoms detected — try describing how you feel in more detail.
          </span>
        </div>
      )}

      {triage && cfg && (
        <div className="triageReveal" style={{
          ...S.triageCard,
          borderColor: cfg.color,
          background: cfg.accent,
          boxShadow: `0 6px 36px ${cfg.glow}, inset 0 1px 0 rgba(255,255,255,0.06)`,
          "--glow": cfg.glow,
        }}>
          {/* Shimmer sweep */}
          <div style={S.shimmer} className="shimmerAnim" />

          <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
            <span style={{ fontSize: 36, filter: `drop-shadow(0 4px 8px ${cfg.glow})`, lineHeight: 1 }}>
              {cfg.icon}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 18, color: cfg.color, letterSpacing: -0.4, marginBottom: 8 }}>
                {cfg.label}
              </div>
              <ScoreBar score={triage.urgency_score} color={cfg.color} />
            </div>
          </div>

          <div style={S.diagRow}>
            <div style={S.diagLabel}>Top Diagnosis</div>
            <div style={S.diagValue}>{triage.top_diagnosis}</div>
          </div>

          <div style={{ ...S.actionBox, borderLeft: `3px solid ${cfg.color}` }}>
            <span style={{ fontSize: 18 }}>📋</span>
            <span style={{ fontSize: 14, fontWeight: 500, color: T.textPrimary }}>{triage.recommended_action}</span>
          </div>

          {triage.differential?.length > 1 && (
            <div style={{ marginTop: 14 }}>
              <div style={S.cardTitle}>Differential Diagnoses</div>
              {triage.differential.map((d, i) => {
                const dc = URGENCY_CONFIG[d.urgency];
                return (
                  <div key={i} className="diffIn" style={{ ...S.diffRow, animationDelay: `${i * 0.08}s` }}>
                    <span style={{ flex: 1, fontSize: 13.5, color: T.textPrimary, fontWeight: 500 }}>{d.disease}</span>
                    <span style={{
                      fontSize: 10, fontWeight: 800, padding: "3px 10px",
                      borderRadius: 99, color: "#fff",
                      background: dc?.color || T.textMuted,
                      boxShadow: `0 2px 10px ${dc?.glow || "rgba(0,0,0,0.2)"}`,
                    }}>{d.urgency}</span>
                    <span style={{ fontSize: 11.5, color: T.textMuted }}>score: {d.match_score?.toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
          )}

          <PdfDownloadButton sessionId={sessionId} />
        </div>
      )}
    </div>
  );
}

// ── PDF Download Button ───────────────────────────────────────────────────
function PdfDownloadButton({ sessionId }) {
  const [status, setStatus] = useState("idle"); // idle | loading | done | error

  const download = async () => {
    setStatus("loading");
    try {
      // Step 1: run triage
      const triageRes = await axios.post(`${API}/triage`, {
        session_id: sessionId,
        symptoms: [],
      }).catch(() => null);

      // Step 2: generate report
      await axios.post(`${API}/report`, { session_id: sessionId });

      // Step 3: download PDF as blob
      const pdfRes = await axios.get(`${API}/report/${sessionId}/pdf`, {
        responseType: "blob",
      });

      const url  = window.URL.createObjectURL(new Blob([pdfRes.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href     = url;
      link.download = `triage-report-${sessionId.slice(0, 8)}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setStatus("done");
      setTimeout(() => setStatus("idle"), 3000);
    } catch (e) {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 3000);
    }
  };

  const label = { idle: "📄 Download Report PDF", loading: "⏳ Generating...", done: "✅ Downloaded!", error: "❌ Failed — Try Again" };
  const bg    = { idle: T.surface, loading: T.surface, done: "hsl(148,70%,52%,0.15)", error: "hsl(0,90%,62%,0.15)" };
  const border= { idle: T.border, loading: T.purple, done: "hsl(148,70%,52%,0.5)", error: "hsl(0,90%,62%,0.5)" };
  const color = { idle: T.textSec, loading: T.purple, done: T.green, error: T.red };

  return (
    <button
      onClick={download}
      disabled={status === "loading"}
      style={{
        width: "100%", padding: "11px 0", marginTop: 14,
        background: bg[status], border: `1.5px solid ${border[status]}`,
        borderRadius: 12, cursor: status === "loading" ? "not-allowed" : "pointer",
        color: color[status], fontWeight: 700, fontSize: 13,
        fontFamily: "'Inter','Segoe UI',sans-serif",
        transition: "all 0.25s ease",
        display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
      }}
      onMouseEnter={e => { if (status === "idle") { e.currentTarget.style.borderColor = T.purple; e.currentTarget.style.color = T.purple; e.currentTarget.style.transform = "translateY(-1px)"; }}}
      onMouseLeave={e => { e.currentTarget.style.borderColor = border[status]; e.currentTarget.style.color = color[status]; e.currentTarget.style.transform = "translateY(0)"; }}
    >
      {status === "loading" && <span style={{ width: 13, height: 13, border: `2px solid ${T.purple}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.7s linear infinite", display: "inline-block" }} />}
      {label[status]}
    </button>
  );
}
// ── Emergency Overlay ─────────────────────────────────────────────────────
function EmergencyOverlay({ triage, onDismiss }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVisible(true), 50); return () => clearTimeout(t); }, []);

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999,
      background: "rgba(0,0,0,0.85)",
      backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 20,
      opacity: visible ? 1 : 0,
      transition: "opacity 0.3s ease",
    }}>
      <div style={{
        background: "hsl(0,30%,8%)",
        border: "2px solid hsl(0,90%,55%)",
        borderRadius: 20,
        padding: "36px 32px",
        maxWidth: 480, width: "100%",
        boxShadow: "0 0 80px hsl(0,90%,55%,0.5), 0 0 160px hsl(0,90%,55%,0.2)",
        textAlign: "center",
        animation: "emergencyPulse 1.5s ease-in-out infinite",
      }}>
        {/* Flashing icon */}
        <div style={{ fontSize: 64, marginBottom: 12, animation: "flashIcon 0.8s ease-in-out infinite" }}>🚨</div>

        <div style={{
          fontSize: 26, fontWeight: 900, color: "hsl(0,90%,62%)",
          letterSpacing: -0.5, marginBottom: 8,
          textTransform: "uppercase",
        }}>EMERGENCY DETECTED</div>

        <div style={{
          fontSize: 15, color: "hsl(0,60%,80%)",
          marginBottom: 24, lineHeight: 1.6,
        }}>
          Your symptoms suggest a <strong>life-threatening emergency</strong>.<br />
          Do not wait. Seek immediate medical attention.
        </div>

        {/* Top diagnosis */}
        {triage?.top_diagnosis && (
          <div style={{
            background: "hsl(0,90%,55%,0.12)",
            border: "1px solid hsl(0,90%,55%,0.3)",
            borderRadius: 10, padding: "10px 16px", marginBottom: 24,
            fontSize: 14, color: "hsl(0,60%,85%)",
          }}>
            Possible condition: <strong>{triage.top_diagnosis}</strong>
          </div>
        )}

        {/* Call buttons */}
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <a href="tel:108" style={{
            flex: 1, padding: "16px 0",
            background: "hsl(0,90%,50%)",
            color: "#fff", fontWeight: 900, fontSize: 20,
            borderRadius: 14, textDecoration: "none",
            boxShadow: "0 6px 28px hsl(0,90%,50%,0.6)",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            transition: "transform 0.15s ease, box-shadow 0.15s ease",
          }}
            onMouseEnter={e => { e.currentTarget.style.transform = "scale(1.04)"; e.currentTarget.style.boxShadow = "0 10px 40px hsl(0,90%,50%,0.8)"; }}
            onMouseLeave={e => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = "0 6px 28px hsl(0,90%,50%,0.6)"; }}
          >
            📞 Call 108
          </a>
          <a href="tel:911" style={{
            flex: 1, padding: "16px 0",
            background: "hsl(0,80%,40%)",
            color: "#fff", fontWeight: 900, fontSize: 20,
            borderRadius: 14, textDecoration: "none",
            boxShadow: "0 6px 28px hsl(0,80%,40%,0.5)",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            transition: "transform 0.15s ease",
          }}
            onMouseEnter={e => e.currentTarget.style.transform = "scale(1.04)"}
            onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
          >
            📞 Call 911
          </a>
        </div>

        {/* Nearest hospital button */}
        <button
          onClick={() => { window.open("https://www.google.com/maps/search/hospital+near+me", "_blank"); }}
          style={{
            width: "100%", padding: "13px 0",
            background: "transparent",
            border: "1.5px solid hsl(0,90%,55%,0.5)",
            color: "hsl(0,60%,80%)", fontWeight: 700, fontSize: 14,
            borderRadius: 12, cursor: "pointer", marginBottom: 16,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          }}
        >
          🗺️ Find Nearest Hospital
        </button>

        {/* Dismiss */}
        <button
          onClick={onDismiss}
          style={{
            background: "transparent", border: "none",
            color: "hsl(0,20%,50%)", fontSize: 13, cursor: "pointer",
            textDecoration: "underline",
          }}
        >
          I understand the risk — continue anyway
        </button>
      </div>
    </div>
  );
}
// ── App ────────────────────────────────────────────────────────────────────
export default function App() {
  const [input, setInput]       = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading]   = useState(false);
  const [focused, setFocused]   = useState(false);
  const [listening, setListening]= useState(false);
  const [sessionId]             = useState(() => Math.random().toString(36).slice(2));
  const [emergency, setEmergency] = useState(null);
  const bottomRef               = useRef(null);
  const inputRef                = useRef(null);
  const recognitionRef          = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(async (text) => {
    const userText = text || input.trim();
    if (!userText || loading) return;
    setInput("");
    setLoading(true);
    const id = uid();
    setMessages(m => [...m, { role: "user", text: userText, id }]);

    try {
      const chatRes = await axios.post(`${API}/chat`, {
        session_id: sessionId, user_input: userText, patient_info: {},
      });
      const data     = chatRes.data;
      const nodes    = data.neo4j_nodes || [];
      const entities = data.extracted_entities || [];
      const triage   = data.triage || null;
      const reply    = data.reply || "";

      setMessages(m => [...m, { role: "bot", text: reply, entities, nodes, triage, id: uid() }]);
      if (triage?.urgency_level === "CRITICAL") setEmergency(triage);
    } catch {
      setMessages(m => [...m, { role: "bot", text: "Error connecting to backend.", error: true, id: uid() }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [input, loading, sessionId]);

  const toggleListening = useCallback(() => {
    // Stop if already listening
    if (listening) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setListening(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessages(m => [...m, {
        role: "bot",
        text: "Voice input is not supported in this browser. Please use Chrome or Edge.",
        error: true, id: uid()
      }]);
      return;
    }

    // Abort any existing instance before creating new one
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (_) {}
      recognitionRef.current = null;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous      = false;  // single utterance — more reliable
    recognition.interimResults  = true;
    recognition.lang            = "en-US";
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;

    let finalTranscript = "";

    recognition.onstart = () => {
      finalTranscript = "";
      setListening(true);
    };

    recognition.onresult = (event) => {
      let interim = "";
      finalTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += t;
        else interim += t;
      }
      // Show interim in real-time, commit final
      setInput(finalTranscript || interim);
    };

    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
      // Refocus input after voice ends
      setTimeout(() => inputRef.current?.focus(), 100);
    };

    recognition.onerror = (event) => {
      setListening(false);
      recognitionRef.current = null;
      if (event.error === "not-allowed" || event.error === "permission-denied") {
        setMessages(m => [...m, {
          role: "bot",
          text: "Microphone access denied. Please allow microphone permission in your browser settings and try again.",
          error: true, id: uid()
        }]);
      } else if (event.error === "no-speech") {
        // Silent — no speech detected, just stop quietly
      } else if (event.error === "network") {
        // Transient Chrome network error — stop silently, user can retry
        setListening(false);
        recognitionRef.current = null;
        setTimeout(() => inputRef.current?.focus(), 100);
      } else if (event.error !== "aborted") {
        setMessages(m => [...m, {
          role: "bot",
          text: `Voice input error: ${event.error}. Please try again.`,
          error: true, id: uid()
        }]);
      }
    };

    try {
      recognition.start();
    } catch (err) {
      setListening(false);
      recognitionRef.current = null;
      console.error("Recognition start failed:", err);
    }
  }, [listening, inputRef]);

  return (
    <div style={S.page}>
      <ParticleCanvas />
      {emergency && <EmergencyOverlay triage={emergency} onDismiss={() => setEmergency(null)} />}

      {/* Background orbs */}
      <div style={S.orb1} /><div style={S.orb2} /><div style={S.orb3} />

      {/* ── Header ── */}
      <header style={S.header}>
        <div style={S.headerInner}>
          <div style={S.logoBox}>
            <span style={{ fontSize: 22 }}>🏥</span>
            <div style={S.logoGlow} />
          </div>
          <div>
            <div style={S.title}>Healthcare Triage Bot</div>
            <div style={S.subtitle}>BioBERT · Neo4j Knowledge Graph · Real-time NER</div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
            <div style={S.liveBadge}>
              <span style={S.liveDot} />
              LIVE
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => { setMessages([]); setEmergency(null); setTimeout(() => inputRef.current?.focus(), 50); }}
                title="Clear chat"
                style={{
                  background: "hsl(0,80%,55%,0.12)",
                  border: "1px solid hsl(0,80%,55%,0.28)",
                  borderRadius: 99, padding: "5px 13px",
                  fontSize: 11, fontWeight: 700, color: "hsl(0,80%,70%)",
                  cursor: "pointer", letterSpacing: 0.5,
                  transition: "background 0.2s ease, transform 0.15s ease",
                }}
                onMouseEnter={e => { e.currentTarget.style.background = "hsl(0,80%,55%,0.22)"; e.currentTarget.style.transform = "scale(1.05)"; }}
                onMouseLeave={e => { e.currentTarget.style.background = "hsl(0,80%,55%,0.12)"; e.currentTarget.style.transform = "scale(1)"; }}
              >
                🗑 Clear Chat
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── Chat ── */}
      <div style={S.chat}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "52px 0 16px" }} className="pageLoad">
            <div style={S.heroIconWrap}>
              <span style={{ fontSize: 60, display: "block", position: "relative", zIndex: 1 }}>🩺</span>
              <div style={S.heroRing} />
              <div style={S.heroRing2} />
            </div>
            <div style={S.heroTitle}>Describe your symptoms</div>
            <div style={S.heroSub}>
              I'll analyze them using BioBERT and our medical knowledge graph
            </div>
            <div style={S.chips}>
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="chip"
                  style={{ ...S.chip, animationDelay: `${0.15 + i * 0.09}s` }}
                  onClick={() => send(s)}
                >{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={msg.id} className="msgSlide" style={{ animationDelay: `${idx * 0.03}s` }}>
            {msg.role === "user" && (
              <div style={S.userRow}>
                <div style={S.userBubble}>{msg.text}</div>
              </div>
            )}
            {msg.role === "bot" && !msg.error && <BotResponse msg={msg} sessionId={sessionId} />}
            {msg.role === "bot" && msg.error && (
              <div style={S.errorBubble}>{msg.text}</div>
            )}
          </div>
        ))}

        {loading && (
          <div style={S.typingRow} className="popIn">
            <div style={S.typingBubble}>
              {[0, 1, 2].map(i => (
                <span key={i} style={{ ...S.dot, animationDelay: `${i * 0.17}s` }} />
              ))}
            </div>
            <span style={{ color: T.textMuted, fontSize: 13 }}>Analyzing symptoms…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input ── */}
      <div style={S.inputBar}>
        <div style={{ ...S.inputWrap, ...(focused ? S.inputWrapFocused : {}) }}>
          <span style={{ fontSize: 17, marginRight: 8, opacity: 0.45 }}>💬</span>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && send()}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Describe your symptoms in plain English…"
            disabled={loading}
            style={S.input}
          />
          <button 
            onClick={toggleListening} 
            title="Use Voice Dictation"
            style={{ ...S.micBtn, ...(listening ? S.micBtnActive : {}) }}
          >
            {listening ? <span className="micPulse">🎙️</span> : <span style={{ opacity: 0.6 }}>🎤</span>}
          </button>
        </div>
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="sendBtn"
          style={{ ...S.sendBtn, opacity: loading || !input.trim() ? 0.4 : 1, cursor: loading || !input.trim() ? "not-allowed" : "pointer" }}
        >
          {loading
            ? <span style={S.spinner} />
            : <span style={{ letterSpacing: 0.5 }}>Send →</span>
          }
        </button>
      </div>

      {/* ── Global CSS ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@700&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        input::placeholder { color: hsl(220,10%,40%); }

        /* ─ Keyframes ─ */
        @keyframes emergencyPulse {
          0%,100% { box-shadow: 0 0 80px hsl(0,90%,55%,0.5), 0 0 160px hsl(0,90%,55%,0.2); }
          50%      { box-shadow: 0 0 120px hsl(0,90%,55%,0.8), 0 0 200px hsl(0,90%,55%,0.4); }
        }
        @keyframes flashIcon {
          0%,100% { transform: scale(1);    filter: drop-shadow(0 0 12px hsl(0,90%,55%,0.8)); }
          50%      { transform: scale(1.15); filter: drop-shadow(0 0 28px hsl(0,90%,55%,1)); }
        }
        @keyframes orbFloat {
          0%,100% { transform: translate(0,0) scale(1); }
          33%      { transform: translate(40px,-30px) scale(1.06); }
          66%      { transform: translate(-20px,20px) scale(0.96); }
        }
        @keyframes orbFloat2 {
          0%,100% { transform: translate(0,0) scale(1); }
          50%      { transform: translate(-40px,30px) scale(1.05); }
        }
        @keyframes logoPulse {
          0%,100% { box-shadow: 0 0 20px hsl(262,90%,66%,0.5); }
          50%      { box-shadow: 0 0 40px hsl(262,90%,66%,0.8), 0 0 14px hsl(185,90%,55%,0.4); }
        }
        @keyframes ring1 {
          0%   { transform: scale(0.8); opacity: 0.6; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        @keyframes ring2 {
          0%   { transform: scale(0.8); opacity: 0.4; }
          100% { transform: scale(2.0); opacity: 0; }
        }
        @keyframes livePulse {
          0%,100% { box-shadow: 0 0 0 0 hsl(148,70%,52%,0.7); }
          50%      { box-shadow: 0 0 0 5px hsl(148,70%,52%,0); }
        }
        @keyframes bounce {
          0%,80%,100% { transform: translateY(0) scale(1); }
          40%          { transform: translateY(-10px) scale(1.2); }
        }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes shimmerMove {
          0%   { left: -100%; }
          100% { left: 200%; }
        }
        @keyframes micPulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50%      { transform: scale(1.2); opacity: 0.8; }
        }

        /* ─ Entrance Animations ─ */
        @keyframes pageLoad {
          from { opacity:0; transform: translateY(30px) scale(0.97); }
          to   { opacity:1; transform: translateY(0) scale(1); }
        }
        @keyframes msgSlide {
          from { opacity:0; transform: translateX(20px); }
          to   { opacity:1; transform: translateX(0); }
        }
        @keyframes revealUp {
          from { opacity:0; transform: translateY(16px); }
          to   { opacity:1; transform: translateY(0); }
        }
        @keyframes tagPop {
          from { opacity:0; transform: scale(0.7); }
          to   { opacity:1; transform: scale(1); }
        }
        @keyframes triageReveal {
          from { opacity:0; transform: translateY(20px) scale(0.96); }
          to   { opacity:1; transform: translateY(0) scale(1); }
        }
        @keyframes diffIn {
          from { opacity:0; transform: translateX(-10px); }
          to   { opacity:1; transform: translateX(0); }
        }
        @keyframes popIn {
          from { opacity:0; transform: scale(0.85); }
          to   { opacity:1; transform: scale(1); }
        }
        @keyframes chipIn {
          from { opacity:0; transform: translateY(14px); }
          to   { opacity:1; transform: translateY(0); }
        }

        .pageLoad   { animation: pageLoad   0.6s cubic-bezier(0.16,1,0.3,1) both; }
        .msgSlide   { animation: msgSlide   0.4s cubic-bezier(0.16,1,0.3,1) both; }
        .revealUp   { animation: revealUp   0.45s cubic-bezier(0.16,1,0.3,1) both; }
        .tagPop     { animation: tagPop     0.35s cubic-bezier(0.34,1.56,0.64,1) both; }
        .triageReveal { animation: triageReveal 0.5s cubic-bezier(0.16,1,0.3,1) both; }
        .diffIn     { animation: diffIn     0.35s cubic-bezier(0.16,1,0.3,1) both; }
        .popIn      { animation: popIn      0.3s cubic-bezier(0.34,1.56,0.64,1) both; }
        .shimmerAnim { animation: shimmerMove 2.4s ease-in-out infinite; }
        .micPulse    { animation: micPulse 1.2s ease-in-out infinite; display: inline-block; filter: drop-shadow(0 0 6px hsl(320,85%,65%,0.6)); }

        /* ─ Chip (suggestion button) ─ */
        .chip { animation: chipIn 0.5s cubic-bezier(0.16,1,0.3,1) both; }
        .chip:hover {
          transform: translateY(-4px) scale(1.05) !important;
          background: linear-gradient(135deg, hsl(262,90%,66%,0.18), hsl(185,90%,55%,0.12)) !important;
          border-color: hsl(262,90%,66%,0.5) !important;
          color: hsl(220,20%,96%) !important;
          box-shadow: 0 8px 28px hsl(262,90%,66%,0.25) !important;
        }
        .chip:active { transform: scale(0.96) !important; }

        /* ─ Send button ─ */
        .sendBtn:not(:disabled):hover {
          transform: translateY(-2px) scale(1.04);
          box-shadow: 0 10px 32px hsl(262,90%,66%,0.55) !important;
          filter: brightness(1.12);
        }
        .sendBtn:not(:disabled):active { transform: scale(0.96); }
        .sendBtn { transition: transform 0.18s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.18s ease, filter 0.18s ease; }

        /* ─ Scrollbar ─ */
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: hsl(228,18%,28%); border-radius: 99px; }
        ::-webkit-scrollbar-thumb:hover { background: hsl(262,90%,66%,0.4); }
      `}</style>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const S = {
  page: {
    display: "flex", flexDirection: "column", height: "100vh",
    background: T.bg, fontFamily: "'Inter','Segoe UI',sans-serif",
    overflow: "hidden", position: "relative", color: T.textPrimary,
  },
  canvas: {
    position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none", opacity: 0.45,
  },
  orb1: {
    position: "fixed", top: -140, left: -100, width: 560, height: 560,
    borderRadius: "50%", background: T.purple, filter: "blur(90px)", opacity: 0.12,
    animation: "orbFloat 16s ease-in-out infinite", pointerEvents: "none", zIndex: 0,
  },
  orb2: {
    position: "fixed", bottom: -120, right: -100, width: 480, height: 480,
    borderRadius: "50%", background: T.cyan, filter: "blur(90px)", opacity: 0.1,
    animation: "orbFloat2 20s ease-in-out infinite", pointerEvents: "none", zIndex: 0,
  },
  orb3: {
    position: "fixed", top: "45%", left: "30%", width: 320, height: 320,
    borderRadius: "50%", background: T.purpleDim, filter: "blur(80px)", opacity: 0.06,
    animation: "orbFloat 24s ease-in-out infinite reverse", pointerEvents: "none", zIndex: 0,
  },

  // Header
  header: {
    position: "relative", zIndex: 10,
    background: "hsl(228,28%,8%,0.75)",
    backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)",
    borderBottom: `1px solid ${T.border}`,
    padding: "14px 24px",
    boxShadow: "0 4px 32px rgba(0,0,0,0.4)",
  },
  headerInner: {
    display: "flex", alignItems: "center", gap: 16,
    maxWidth: 840, margin: "0 auto",
  },
  logoBox: {
    width: 44, height: 44, borderRadius: 14, flexShrink: 0,
    background: `linear-gradient(135deg, ${T.purple}, ${T.cyan})`,
    display: "grid", placeItems: "center", position: "relative",
    animation: "logoPulse 3s ease-in-out infinite",
  },
  logoGlow: {
    position: "absolute", inset: -6, borderRadius: 18,
    background: `radial-gradient(circle, ${T.purpleGlow}, transparent 70%)`,
    animation: "ring1 2.5s ease-out infinite",
  },
  title: { fontFamily: "'Outfit','Inter',sans-serif", fontWeight: 700, fontSize: 20, letterSpacing: -0.4 },
  subtitle: { color: T.textMuted, fontSize: 12 },
  liveBadge: {
    display: "flex", alignItems: "center", gap: 7,
    background: "hsl(148,70%,52%,0.12)",
    border: "1px solid hsl(148,70%,52%,0.28)",
    borderRadius: 99, padding: "5px 13px",
    fontSize: 11, fontWeight: 700, color: T.green, letterSpacing: 1,
  },
  liveDot: {
    width: 8, height: 8, borderRadius: "50%", background: T.green,
    display: "inline-block", animation: "livePulse 1.6s ease-in-out infinite",
  },

  // Chat
  chat: {
    flex: 1, overflowY: "auto", padding: "24px 16px",
    maxWidth: 840, width: "100%", margin: "0 auto", boxSizing: "border-box",
    position: "relative", zIndex: 1,
  },

  // Welcome / hero
  heroIconWrap: { position: "relative", display: "inline-block", marginBottom: 20 },
  heroRing: {
    position: "absolute", inset: -12, borderRadius: "50%",
    border: `2px solid ${T.purpleGlow}`,
    animation: "ring1 2.2s ease-out infinite",
  },
  heroRing2: {
    position: "absolute", inset: -24, borderRadius: "50%",
    border: `1.5px solid hsl(262,90%,66%,0.2)`,
    animation: "ring2 2.4s ease-out infinite 0.4s",
  },
  heroTitle: {
    fontFamily: "'Outfit','Inter',sans-serif", fontSize: 27, fontWeight: 700,
    letterSpacing: -0.5, marginBottom: 10,
    background: `linear-gradient(90deg, ${T.textPrimary}, ${T.cyan})`,
    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
  },
  heroSub: { color: T.textSec, fontSize: 15, marginBottom: 28, lineHeight: 1.6 },
  chips: { display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center" },
  chip: {
    background: T.surface, border: `1px solid ${T.border}`,
    borderRadius: 99, padding: "9px 18px", fontSize: 13, cursor: "pointer",
    color: T.textSec, outline: "none",
    transition: "transform 0.2s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.2s ease, background 0.2s ease, border-color 0.2s ease, color 0.2s ease",
  },

  // User bubble
  userRow: { display: "flex", justifyContent: "flex-end", marginBottom: 14 },
  userBubble: {
    background: `linear-gradient(135deg, ${T.purple}, ${T.purpleDim})`,
    color: "#fff", padding: "13px 20px",
    borderRadius: "20px 20px 5px 20px",
    maxWidth: "70%", fontSize: 15, lineHeight: 1.55, fontWeight: 500,
    boxShadow: `0 4px 24px ${T.purpleGlow}`,
  },

  // Bot bubble
  botBubbleWrap: { display: "flex", justifyContent: "flex-start", marginBottom: 14 },
  botBubble: {
    background: "rgba(255,255,255,0.06)",
    backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
    border: `1px solid ${T.border}`,
    color: T.textPrimary, padding: "13px 20px",
    borderRadius: "20px 20px 20px 5px",
    maxWidth: "85%", fontSize: 15, lineHeight: 1.55, fontWeight: 400,
  },

  // Cards
  card: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 14, padding: "16px 18px", marginBottom: 10,
    boxShadow: "0 4px 20px rgba(0,0,0,0.25)",
    backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
  },
  cardTitle: {
    fontSize: 10.5, fontWeight: 700, color: T.textMuted,
    textTransform: "uppercase", letterSpacing: 1.3, marginBottom: 10,
  },
  tag: {
    background: `linear-gradient(135deg, hsl(262,90%,66%,0.18), hsl(185,90%,55%,0.14))`,
    color: "hsl(220,80%,80%)", padding: "5px 14px", borderRadius: 99,
    fontSize: 13, fontWeight: 600,
    border: `1px solid hsl(262,90%,66%,0.28)`,
    boxShadow: `0 2px 10px hsl(262,90%,66%,0.12)`,
  },

  // Triage card
  triageCard: {
    borderRadius: 16, padding: 22, marginBottom: 10,
    border: "1.5px solid",
    position: "relative", overflow: "hidden",
    backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
  },
  shimmer: {
    position: "absolute", top: 0, bottom: 0, width: "45%",
    background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)",
    pointerEvents: "none",
  },

  // Score bar
  scoreWrap: { display: "flex", alignItems: "center", gap: 10 },
  scoreTrack: {
    width: 150, height: 5, background: "rgba(255,255,255,0.08)",
    borderRadius: 99, overflow: "hidden",
  },
  scoreFill: { height: "100%", borderRadius: 99 },

  // Diagnosis
  diagRow: { marginBottom: 12 },
  diagLabel: { fontSize: 10.5, color: T.textMuted, textTransform: "uppercase", letterSpacing: 1.1, marginBottom: 4 },
  diagValue: { fontSize: 22, fontWeight: 800, letterSpacing: -0.5, color: T.textPrimary },
  actionBox: {
    display: "flex", alignItems: "center", gap: 10,
    background: "rgba(255,255,255,0.05)", borderRadius: 10,
    padding: "11px 15px", marginBottom: 2,
  },
  diffRow: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "8px 0", borderBottom: `1px solid ${T.border}`,
  },

  // Typing
  typingRow: { display: "flex", alignItems: "center", gap: 12, padding: "8px 0" },
  typingBubble: {
    display: "flex", gap: 5, padding: "11px 16px",
    background: T.surface, border: `1px solid ${T.border}`,
    borderRadius: 24, boxShadow: "0 2px 12px rgba(0,0,0,0.2)",
  },
  dot: {
    width: 9, height: 9,
    background: `linear-gradient(135deg, ${T.purple}, ${T.cyan})`,
    borderRadius: "50%", display: "inline-block",
    animation: "bounce 1.3s ease-in-out infinite",
    boxShadow: `0 0 8px ${T.purpleGlow}`,
  },

  // Input bar
  inputBar: {
    position: "relative", zIndex: 10,
    display: "flex", gap: 10, padding: "13px 16px 17px",
    background: "hsl(228,28%,8%,0.8)",
    backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)",
    borderTop: `1px solid ${T.border}`,
    maxWidth: 840, width: "100%", margin: "0 auto", boxSizing: "border-box",
  },
  inputWrap: {
    flex: 1, display: "flex", alignItems: "center",
    background: T.surface, border: `1.5px solid ${T.border}`,
    borderRadius: 28, padding: "0 18px",
    transition: "border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease",
  },
  inputWrapFocused: {
    borderColor: T.purple,
    boxShadow: `0 0 0 3px ${T.purpleGlow}`,
    background: T.surface2,
  },
  input: {
    flex: 1, padding: "13px 0", background: "transparent",
    border: "none", outline: "none",
    fontSize: 15, color: T.textPrimary,
    fontFamily: "'Inter','Segoe UI',sans-serif",
  },
  micBtn: {
    padding: "6px 8px", background: "transparent", border: "none", outline: "none",
    cursor: "pointer", fontSize: 18, transition: "transform 0.2s",
    display: "flex", alignItems: "center", justifyContent: "center",
  },
  micBtnActive: {
    transform: "scale(1.1)",
  },
  sendBtn: {
    padding: "13px 28px", borderRadius: 28, border: "none",
    background: `linear-gradient(135deg, ${T.purple}, ${T.purpleDim})`,
    color: "#fff", fontWeight: 700, fontSize: 15,
    boxShadow: `0 4px 20px ${T.purpleGlow}`,
    display: "flex", alignItems: "center", justifyContent: "center",
    minWidth: 100, fontFamily: "'Inter','Segoe UI',sans-serif",
  },
  spinner: {
    width: 16, height: 16,
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff", borderRadius: "50%",
    animation: "spin 0.7s linear infinite", display: "inline-block",
  },
  errorBubble: {
    background: "hsl(0,90%,62%,0.1)", border: "1px solid hsl(0,90%,62%,0.3)",
    borderRadius: 12, padding: 14, color: "hsl(0,90%,72%)", fontSize: 14,
    backdropFilter: "blur(8px)",
  },
};
