import React, { useState } from "react";
import axios from "axios";

const API = "http://localhost:8000";

export default function App() {
  const [symptom, setSymptom] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const query = async () => {
    if (!symptom.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await axios.get(`${API}/graph/symptom/${symptom.toLowerCase()}`);
      setResult(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || "Error querying backend");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: "40px auto", fontFamily: "sans-serif", padding: 24 }}>
      <h1>🏥 Healthcare Triage Bot</h1>
      <h3>Knowledge Graph Query</h3>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          value={symptom}
          onChange={e => setSymptom(e.target.value)}
          onKeyDown={e => e.key === "Enter" && query()}
          placeholder="Enter symptom (e.g. fever, chest pain)"
          style={{ flex: 1, padding: "8px 12px", fontSize: 16, borderRadius: 6, border: "1px solid #ccc" }}
        />
        <button
          onClick={query}
          style={{ padding: "8px 20px", fontSize: 16, borderRadius: 6, background: "#0070f3", color: "#fff", border: "none", cursor: "pointer" }}
        >
          {loading ? "..." : "Query"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {result && (
        <div>
          <h4>Diseases linked to: <em>{result.symptom}</em></h4>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f0f0f0" }}>
                <th style={th}>Disease</th>
                <th style={th}>Urgency</th>
                <th style={th}>Confidence</th>
                <th style={th}>Action</th>
              </tr>
            </thead>
            <tbody>
              {result.diseases.map((d, i) => (
                <tr key={i} style={{ background: urgencyColor(d.urgency) }}>
                  <td style={td}>{d.disease}</td>
                  <td style={td}><strong>{d.urgency}</strong></td>
                  <td style={td}>{(d.confidence * 100).toFixed(0)}%</td>
                  <td style={td}>{d.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const th = { padding: "8px 12px", textAlign: "left", border: "1px solid #ddd" };
const td = { padding: "8px 12px", border: "1px solid #ddd" };
const urgencyColor = u => ({ CRITICAL: "#ffe0e0", HIGH: "#fff3e0", MEDIUM: "#fffde0", LOW: "#e8f5e9" }[u] || "#fff");
