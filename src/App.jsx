import { useState, useEffect, useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const CANDIDATES = [
  { id: "harris",    name: "Kamala Harris",            short: "Harris",    color: "#1a6bff" },
  { id: "newsom",    name: "Gavin Newsom",              short: "Newsom",    color: "#e63946" },
  { id: "buttigieg", name: "Pete Buttigieg",            short: "Buttigieg", color: "#f4a261" },
  { id: "ocasio",    name: "Alexandria Ocasio-Cortez",  short: "AOC",       color: "#2a9d8f" },
  { id: "shapiro",   name: "Josh Shapiro",              short: "Shapiro",   color: "#9b5de5" },
  { id: "pritzker",  name: "J.B. Pritzker",             short: "Pritzker",  color: "#e9c46a" },
  { id: "booker",    name: "Cory Booker",               short: "Booker",    color: "#f77f00" },
  { id: "whitmer",   name: "Gretchen Whitmer",          short: "Whitmer",   color: "#06d6a0" },
  { id: "beshear",   name: "Andy Beshear",              short: "Beshear",   color: "#ef476f" },
  { id: "kelly",     name: "Mark Kelly",                short: "Kelly",     color: "#118ab2" },
];

function weightedAverage(polls, candId) {
  if (!polls.length) return null;
  let totalWeight = 0, weightedSum = 0;
  const now = new Date();
  polls.forEach(p => {
    const val = parseFloat(p[candId]);
    if (isNaN(val)) return;
    const age = (now - new Date(p.date)) / (1000 * 60 * 60 * 24);
    const recency = Math.exp(-age / 60);
    const size = Math.sqrt(parseFloat(p.sampleSize) || 500);
    const w = recency * size;
    totalWeight += w;
    weightedSum += val * w;
  });
  return totalWeight > 0 ? (weightedSum / totalWeight).toFixed(1) : null;
}

function formatDate(d) {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[parseInt(m)-1]} ${parseInt(day)}, ${y}`;
}

const labelStyle = { display:"block", fontSize:10, color:"#666", fontFamily:"monospace", letterSpacing:"0.1em", marginBottom:4, textTransform:"uppercase" };
const inputStyle = { background:"#0a0a0f", border:"1px solid #333", color:"#e8e6df", padding:"8px 10px", fontFamily:"monospace", fontSize:13, width:"100%", boxSizing:"border-box", outline:"none" };
const thStyle   = { textAlign:"left", padding:"8px 12px", color:"#666", borderBottom:"1px solid #333", fontWeight:"normal", letterSpacing:"0.1em", fontSize:11 };
const tdStyle   = { padding:"8px 12px", color:"#e8e6df" };

const EMPTY_POLL = { pollster:"", date:"", sampleSize:"", harris:"", newsom:"", buttigieg:"", ocasio:"", shapiro:"", pritzker:"", booker:"", whitmer:"", beshear:"", kelly:"" };

export default function PollingTracker() {
  const [polls, setPolls]               = useState([]);
  const [loaded, setLoaded]             = useState(false);
  const [lastUpdated, setLastUpdated]   = useState(null);
  const [showForm, setShowForm]         = useState(false);
  const [form, setForm]                 = useState(EMPTY_POLL);
  const [activeTab, setActiveTab]       = useState("chart");
  const [visibleCands, setVisibleCands] = useState(CANDIDATES.map(c => c.id));
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [manualPolls, setManualPolls]   = useState([]);

  // Load polls.json (auto-fetched by GitHub Actions) + any manual additions from localStorage
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/polls.json?t=" + Date.now());
        const data = await res.json();
        setPolls(data);
        setLastUpdated(new Date().toLocaleDateString());
      } catch {
        setPolls([]);
      }
      // Load any manual polls saved locally
      try {
        const saved = localStorage.getItem("manual-polls-2028");
        if (saved) setManualPolls(JSON.parse(saved));
      } catch {}
      setLoaded(true);
    }
    load();
  }, []);

  const allPolls = useMemo(() => {
    const combined = [...polls, ...manualPolls];
    return combined.sort((a, b) => new Date(a.date) - new Date(b.date));
  }, [polls, manualPolls]);

  function addManualPoll() {
    const newPoll = { ...form, id: `manual-${Date.now()}` };
    const updated = [...manualPolls, newPoll];
    setManualPolls(updated);
    localStorage.setItem("manual-polls-2028", JSON.stringify(updated));
    setForm(EMPTY_POLL);
    setShowForm(false);
  }

  function deleteManualPoll(id) {
    const updated = manualPolls.filter(p => p.id !== id);
    setManualPolls(updated);
    localStorage.setItem("manual-polls-2028", JSON.stringify(updated));
    setDeleteConfirm(null);
  }

  const averages = useMemo(() =>
    CANDIDATES.map(c => ({ ...c, avg: weightedAverage(allPolls, c.id) }))
      .filter(c => c.avg !== null)
      .sort((a, b) => parseFloat(b.avg) - parseFloat(a.avg)),
  [allPolls]);

  const chartData = useMemo(() =>
    [...allPolls].sort((a,b) => new Date(a.date)-new Date(b.date)).map(p => {
      const row = { date: p.date, label: formatDate(p.date), pollster: p.pollster };
      CANDIDATES.forEach(c => { row[c.id] = parseFloat(p[c.id]) || null; });
      return row;
    }),
  [allPolls]);

  const formValid = form.pollster && form.date && CANDIDATES.some(c => form[c.id]);

  if (!loaded) return (
    <div style={{ background:"#0a0a0f", minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", color:"#fff", fontFamily:"Georgia, serif", fontSize:18 }}>
      Loading tracker...
    </div>
  );

  return (
    <div style={{ background:"#0a0a0f", minHeight:"100vh", color:"#e8e6df", fontFamily:"'Georgia','Times New Roman',serif" }}>

      {/* Header */}
      <div style={{ borderBottom:"3px solid #1a6bff", padding:"28px 36px 18px" }}>
        <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", flexWrap:"wrap", gap:12 }}>
          <div>
            <div style={{ fontSize:11, letterSpacing:"0.2em", textTransform:"uppercase", color:"#1a6bff", fontFamily:"monospace", marginBottom:4 }}>
              2028 Presidential Primary
            </div>
            <h1 style={{ margin:0, fontSize:"clamp(22px,4vw,36px)", fontWeight:"bold", letterSpacing:"-0.02em", lineHeight:1.1 }}>
              Democratic Primary<br/>
              <span style={{ color:"#1a6bff" }}>Polling Tracker</span>
            </h1>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            style={{ background: showForm ? "#333" : "#1a6bff", color:"#fff", border:"none", padding:"10px 20px", cursor:"pointer", fontFamily:"monospace", fontSize:13, letterSpacing:"0.05em", fontWeight:"bold" }}
          >
            {showForm ? "✕ CANCEL" : "+ ADD POLL"}
          </button>
        </div>
        <div style={{ marginTop:10, fontSize:12, color:"#888", fontFamily:"monospace", display:"flex", gap:24 }}>
          <span>{allPolls.length} poll{allPolls.length !== 1 ? "s" : ""} tracked</span>
          <span style={{ color:"#2a9d8f" }}>⟳ Auto-updated daily via GitHub Actions</span>
          {lastUpdated && <span>Last loaded: {lastUpdated}</span>}
        </div>
      </div>

      {/* Add Poll Form */}
      {showForm && (
        <div style={{ background:"#111118", borderBottom:"1px solid #222", padding:"24px 36px" }}>
          <div style={{ fontSize:13, fontFamily:"monospace", color:"#1a6bff", marginBottom:16, letterSpacing:"0.1em" }}>
            MANUAL POLL ENTRY
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(160px,1fr))", gap:12, marginBottom:16 }}>
            <div><label style={labelStyle}>Pollster</label><input value={form.pollster} onChange={e=>setForm(f=>({...f,pollster:e.target.value}))} style={inputStyle} placeholder="e.g. Harvard Harris"/></div>
            <div><label style={labelStyle}>Date</label><input type="date" value={form.date} onChange={e=>setForm(f=>({...f,date:e.target.value}))} style={inputStyle}/></div>
            <div><label style={labelStyle}>Sample Size</label><input type="number" value={form.sampleSize} onChange={e=>setForm(f=>({...f,sampleSize:e.target.value}))} style={inputStyle} placeholder="e.g. 1200"/></div>
          </div>
          <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", marginBottom:8, letterSpacing:"0.1em" }}>CANDIDATE NUMBERS (%) — leave blank if not polled</div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(140px,1fr))", gap:10 }}>
            {CANDIDATES.map(c => (
              <div key={c.id}>
                <label style={{ ...labelStyle, color:c.color }}>{c.short}</label>
                <input type="number" value={form[c.id]} onChange={e=>setForm(f=>({...f,[c.id]:e.target.value}))} style={{ ...inputStyle, borderColor: form[c.id] ? c.color : "#333" }} placeholder="%" min="0" max="100"/>
              </div>
            ))}
          </div>
          <div style={{ marginTop:16 }}>
            <button onClick={addManualPoll} disabled={!formValid} style={{ background: formValid?"#1a6bff":"#333", color: formValid?"#fff":"#666", border:"none", padding:"10px 28px", cursor: formValid?"pointer":"not-allowed", fontFamily:"monospace", fontSize:13, fontWeight:"bold", letterSpacing:"0.1em" }}>
              SAVE POLL
            </button>
          </div>
        </div>
      )}

      {/* Averages */}
      <div style={{ padding:"24px 36px 0", overflowX:"auto" }}>
        <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.15em", marginBottom:14 }}>WEIGHTED POLLING AVERAGE · click to show/hide on chart</div>
        <div style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
          {averages.map((c,i) => (
            <div key={c.id} onClick={() => setVisibleCands(prev => prev.includes(c.id) ? prev.filter(x=>x!==c.id) : [...prev,c.id])} style={{ background: i===0 ? `${c.color}20` : "#111118", border:`1px solid ${i===0?c.color:"#222"}`, padding:"14px 18px", minWidth:120, cursor:"pointer", opacity: visibleCands.includes(c.id)?1:0.35, transition:"all 0.15s" }}>
              <div style={{ fontSize:10, color:c.color, fontFamily:"monospace", letterSpacing:"0.1em", marginBottom:4 }}>{i===0?"● LEADER":`#${i+1}`}</div>
              <div style={{ fontSize:24, fontWeight:"bold", color:c.color, lineHeight:1 }}>{c.avg}%</div>
              <div style={{ fontSize:12, color:"#aaa", marginTop:4 }}>{c.short}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding:"24px 36px 0", display:"flex", gap:0, borderBottom:"1px solid #222", marginTop:24 }}>
        {["chart","table"].map(tab => (
          <button key={tab} onClick={()=>setActiveTab(tab)} style={{ background:"none", border:"none", borderBottom: activeTab===tab?"2px solid #1a6bff":"2px solid transparent", color: activeTab===tab?"#e8e6df":"#666", padding:"8px 20px", cursor:"pointer", fontFamily:"monospace", fontSize:12, letterSpacing:"0.1em", textTransform:"uppercase" }}>
            {tab}
          </button>
        ))}
      </div>

      {/* Chart */}
      {activeTab === "chart" && (
        <div style={{ padding:"24px 36px" }}>
          {chartData.length < 2 ? (
            <div style={{ color:"#555", fontFamily:"monospace", fontSize:13, padding:"40px 0" }}>Add at least 2 polls to see trend lines.</div>
          ) : (
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={chartData} margin={{ top:10, right:20, left:0, bottom:10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a22"/>
                <XAxis dataKey="label" tick={{ fill:"#666", fontSize:11, fontFamily:"monospace" }} tickLine={false}/>
                <YAxis tick={{ fill:"#666", fontSize:11, fontFamily:"monospace" }} tickLine={false} unit="%" domain={[0,"auto"]}/>
                <Tooltip contentStyle={{ background:"#111118", border:"1px solid #333", fontFamily:"monospace", fontSize:12 }} labelStyle={{ color:"#aaa", marginBottom:6 }} formatter={(val,name) => { const c=CANDIDATES.find(c=>c.id===name); return [`${val}%`,c?.short||name]; }}/>
                {CANDIDATES.filter(c=>visibleCands.includes(c.id)).map(c => (
                  <Line key={c.id} type="monotone" dataKey={c.id} stroke={c.color} strokeWidth={2} dot={{ r:4, fill:c.color, strokeWidth:0 }} connectNulls activeDot={{ r:6 }}/>
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Table */}
      {activeTab === "table" && (
        <div style={{ padding:"24px 36px", overflowX:"auto" }}>
          <table style={{ borderCollapse:"collapse", width:"100%", fontFamily:"monospace", fontSize:12 }}>
            <thead>
              <tr>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Pollster</th>
                <th style={thStyle}>N</th>
                {CANDIDATES.map(c=><th key={c.id} style={{ ...thStyle, color:c.color }}>{c.short}</th>)}
                <th style={thStyle}>Source</th>
                <th style={thStyle}></th>
              </tr>
            </thead>
            <tbody>
              {[...allPolls].sort((a,b)=>new Date(b.date)-new Date(a.date)).map(p=>{
                const isManual = p.id?.startsWith("manual-");
                return (
                  <tr key={p.id} style={{ borderBottom:"1px solid #1a1a22" }}>
                    <td style={tdStyle}>{formatDate(p.date)}</td>
                    <td style={tdStyle}>
                      {p.pollster}
                      {isManual && <span style={{ fontSize:9, color:"#555", fontFamily:"monospace", marginLeft:6 }}>manual</span>}
                    </td>
                    <td style={{ ...tdStyle, color:"#666" }}>{p.sampleSize ? Number(p.sampleSize).toLocaleString() : "—"}</td>
                    {CANDIDATES.map(c=>{
                      const val = parseFloat(p[c.id]);
                      const isLeader = !isNaN(val) && CANDIDATES.every(o=>o.id===c.id||isNaN(parseFloat(p[o.id]))||parseFloat(p[o.id])<=val);
                      return <td key={c.id} style={{ ...tdStyle, color: !isNaN(val)?(isLeader?c.color:"#e8e6df"):"#333", fontWeight:isLeader?"bold":"normal" }}>{!isNaN(val)?`${val}%`:"—"}</td>;
                    })}
                    <td style={tdStyle}>
                      {p.source_url ? <a href={p.source_url} target="_blank" rel="noreferrer" style={{ color:"#1a6bff", textDecoration:"none", fontSize:11 }}>↗ link</a> : "—"}
                    </td>
                    <td style={tdStyle}>
                      {isManual && (
                        deleteConfirm===p.id
                          ? <span><span style={{ color:"#e63946", cursor:"pointer", marginRight:8 }} onClick={()=>deleteManualPoll(p.id)}>confirm</span><span style={{ color:"#666", cursor:"pointer" }} onClick={()=>setDeleteConfirm(null)}>cancel</span></span>
                          : <span style={{ color:"#444", cursor:"pointer" }} onClick={()=>setDeleteConfirm(p.id)}>✕</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr style={{ borderTop:"2px solid #333" }}>
                <td colSpan={3} style={{ ...tdStyle, color:"#1a6bff", letterSpacing:"0.1em" }}>AVERAGE</td>
                {CANDIDATES.map(c=><td key={c.id} style={{ ...tdStyle, color:c.color, fontWeight:"bold" }}>{weightedAverage(allPolls,c.id)?`${weightedAverage(allPolls,c.id)}%`:"—"}</td>)}
                <td colSpan={2} style={tdStyle}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Footer */}
      <div style={{ padding:"16px 36px 32px", borderTop:"1px solid #1a1a22", marginTop:8 }}>
        <div style={{ fontSize:11, color:"#444", fontFamily:"monospace" }}>
          Auto-polls fetched by GitHub Actions + Anthropic API · Manual additions saved in browser · Weighted by recency (60-day half-life) × sample size · No candidates have formally declared as of Feb 2026
        </div>
      </div>
    </div>
  );
}
