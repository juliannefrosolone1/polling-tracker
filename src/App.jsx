import { useState, useEffect, useMemo, useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from "recharts";

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
  { id: "moore",     name: "Wes Moore",                 short: "Moore",     color: "#43aa8b" },
  { id: "slotkin",   name: "Elissa Slotkin",            short: "Slotkin",   color: "#ff6b6b" },
  { id: "sanders",   name: "Bernie Sanders",            short: "Sanders",   color: "#c77dff" },
  { id: "gallego",   name: "Ruben Gallego",             short: "Gallego",   color: "#ff9f1c" },
  { id: "warnock",   name: "Raphael Warnock",           short: "Warnock",   color: "#2ec4b6" },
  { id: "ossoff",    name: "Jon Ossoff",                short: "Ossoff",    color: "#e71d36" },
  { id: "klobuchar", name: "Amy Klobuchar",             short: "Klobuchar", color: "#8338ec" },
  { id: "khanna",    name: "Ro Khanna",                 short: "Khanna",    color: "#fb5607" },
  { id: "cooper",    name: "Roy Cooper",                short: "Cooper",    color: "#3a86ff" },
  { id: "murphy",    name: "Chris Murphy",              short: "Murphy",    color: "#06d6a0" },
  { id: "stewart",   name: "Jon Stewart",               short: "Stewart",   color: "#ffbe0b" },
];

const DEMO_CATEGORIES = ["gender", "age", "race", "education", "ideology"];
const DEMO_LABELS = { gender: "Gender", age: "Age Group", race: "Race / Ethnicity", education: "Education", ideology: "Political Ideology" };
const GROUP_COLORS = ["#1a6bff","#e63946","#2a9d8f","#f4a261","#9b5de5","#e9c46a"];

// localStorage key for local edits
const LS_KEY = "poll_delta_2028_v2";

function loadDelta() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) return JSON.parse(saved);
  } catch {}
  return { edits: {}, additions: [], deletions: [] };
}

function saveDelta(delta) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(delta)); } catch {}
}

function weightedAverage(polls, candId) {
  if (!polls.length) return null;
  let totalWeight = 0, weightedSum = 0;
  const now = new Date();
  polls.forEach(p => {
    const val = parseFloat(p[candId]);
    if (isNaN(val)) return;
    const ageDays = (now - new Date(p.date)) / (1000 * 60 * 60 * 24);
    const recency = Math.exp(-ageDays / 60);
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

function getDemoValue(poll, candId, demoFilter) {
  if (!demoFilter) return parseFloat(poll[candId]) ?? null;
  const ct = poll?.crosstabs?.[candId]?.[demoFilter.category]?.[demoFilter.group];
  return ct != null ? parseFloat(ct) : null;
}

function weightedAverageDemo(polls, candId, demoFilter) {
  if (!polls.length) return null;
  let totalWeight = 0, weightedSum = 0;
  const now = new Date();
  polls.forEach(p => {
    const val = getDemoValue(p, candId, demoFilter);
    if (val === null || isNaN(val)) return;
    const ageDays = (now - new Date(p.date)) / (1000 * 60 * 60 * 24);
    const recency = Math.exp(-ageDays / 60);
    const size = Math.sqrt(parseFloat(p.sampleSize) || 500);
    const w = recency * size;
    totalWeight += w;
    weightedSum += val * w;
  });
  return totalWeight > 0 ? (weightedSum / totalWeight).toFixed(1) : null;
}

const DEMO_FILTERS = [
  { category: "gender",    group: "Men" },
  { category: "gender",    group: "Women" },
  { category: "age",       group: "18-34" },
  { category: "age",       group: "35-49" },
  { category: "age",       group: "50-64" },
  { category: "age",       group: "65+" },
  { category: "race",      group: "White" },
  { category: "race",      group: "Black" },
  { category: "race",      group: "Hispanic" },
  { category: "race",      group: "Other" },
  { category: "education", group: "No college" },
  { category: "education", group: "Some college" },
  { category: "education", group: "College grad" },
  { category: "education", group: "Postgrad" },
  { category: "ideology",  group: "Very liberal" },
  { category: "ideology",  group: "Somewhat liberal" },
  { category: "ideology",  group: "Moderate" },
  { category: "ideology",  group: "Conservative" },
];

const DEMO_CATEGORY_LABELS = {
  gender: "GENDER", age: "AGE", race: "RACE", education: "EDUCATION", ideology: "IDEOLOGY"
};

const thStyle = { textAlign:"left", padding:"8px 12px", color:"#666", borderBottom:"1px solid #333", fontWeight:"normal", letterSpacing:"0.1em", fontSize:11 };
const tdStyle = { padding:"8px 12px", color:"#e8e6df" };
const inputStyle = { background:"#0a0a0f", border:"1px solid #333", color:"#e8e6df", padding:"8px 10px", fontFamily:"monospace", fontSize:13, width:"100%", boxSizing:"border-box", outline:"none" };
const labelStyle = { display:"block", fontSize:10, color:"#666", fontFamily:"monospace", letterSpacing:"0.1em", marginBottom:4, textTransform:"uppercase" };

const EMPTY_FORM = () => ({ pollster:"", date:"", state:"National", sampleSize:"", source_url:"",
  ...Object.fromEntries(CANDIDATES.map(c => [c.id, ""])) });


// ─── POLL EDIT MODAL ──────────────────────────────────────────────────────────

function PollEditModal({ poll, onSave, onDelete, onClose }) {
  const isNew = !poll.id || poll.id === "__new__";
  const [form, setForm] = useState(() => {
    const f = EMPTY_FORM();
    if (!isNew) {
      Object.assign(f, {
        pollster: poll.pollster || "",
        date: poll.date || "",
        state: poll.state || "National",
        sampleSize: poll.sampleSize || "",
        source_url: poll.source_url || "",
      });
      CANDIDATES.forEach(c => { f[c.id] = poll[c.id] != null ? String(poll[c.id]) : ""; });
    }
    return f;
  });
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const valid = form.pollster.trim() && form.date.trim();

  function handleSave() {
    const saved = {
      ...poll,
      pollster: form.pollster.trim(),
      date: form.date,
      state: form.state.trim() || "National",
      sampleSize: form.sampleSize ? parseInt(form.sampleSize) : null,
      source_url: form.source_url.trim() || null,
    };
    CANDIDATES.forEach(c => {
      const v = form[c.id];
      saved[c.id] = v !== "" && v !== null ? parseFloat(v) : null;
    });
    onSave(saved);
  }

  function set(field, val) { setForm(f => ({ ...f, [field]: val })); }

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.85)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center", padding:20 }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background:"#111118", border:"1px solid #333", width:"100%", maxWidth:820, maxHeight:"90vh", overflowY:"auto", padding:28 }}>
        {/* Header */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20, borderBottom:"1px solid #222", paddingBottom:16 }}>
          <div style={{ fontFamily:"monospace", fontSize:13, color:"#1a6bff", letterSpacing:"0.15em" }}>
            {isNew ? "ADD NEW POLL" : "EDIT POLL"}
          </div>
          <button onClick={onClose} style={{ background:"none", border:"none", color:"#666", cursor:"pointer", fontSize:18, padding:"0 4px" }}>✕</button>
        </div>

        {/* Metadata */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(160px,1fr))", gap:12, marginBottom:20 }}>
          <div>
            <label style={labelStyle}>Pollster *</label>
            <input value={form.pollster} onChange={e=>set("pollster",e.target.value)} style={inputStyle} placeholder="e.g. UNH Survey Center"/>
          </div>
          <div>
            <label style={labelStyle}>Date *</label>
            <input type="date" value={form.date} onChange={e=>set("date",e.target.value)} style={inputStyle}/>
          </div>
          <div>
            <label style={labelStyle}>State / Geography</label>
            <input value={form.state} onChange={e=>set("state",e.target.value)} style={inputStyle} placeholder="National or state name"/>
          </div>
          <div>
            <label style={labelStyle}>Sample Size</label>
            <input type="number" value={form.sampleSize} onChange={e=>set("sampleSize",e.target.value)} style={inputStyle} placeholder="e.g. 635"/>
          </div>
          <div style={{ gridColumn:"span 2" }}>
            <label style={labelStyle}>Source URL</label>
            <input value={form.source_url} onChange={e=>set("source_url",e.target.value)} style={inputStyle} placeholder="https://..."/>
          </div>
        </div>

        {/* Candidate numbers */}
        <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", marginBottom:10, letterSpacing:"0.1em" }}>
          CANDIDATE NUMBERS (%) — leave blank if not tested
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(130px,1fr))", gap:10, marginBottom:24 }}>
          {CANDIDATES.map(c => (
            <div key={c.id}>
              <label style={{ ...labelStyle, color: form[c.id] !== "" ? c.color : "#555" }}>{c.short}</label>
              <input
                type="number" min="0" max="100" step="0.1"
                value={form[c.id]}
                onChange={e => set(c.id, e.target.value)}
                style={{ ...inputStyle, borderColor: form[c.id] !== "" ? c.color : "#333" }}
                placeholder="—"
              />
            </div>
          ))}
        </div>

        {/* Actions */}
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", borderTop:"1px solid #222", paddingTop:16 }}>
          {/* Delete */}
          <div>
            {!isNew && (
              deleteConfirm
                ? <span>
                    <span style={{ fontSize:12, color:"#e63946", fontFamily:"monospace", marginRight:12 }}>Delete this poll?</span>
                    <button onClick={onDelete} style={{ background:"#e63946", color:"#fff", border:"none", padding:"8px 16px", cursor:"pointer", fontFamily:"monospace", fontSize:12, marginRight:8 }}>CONFIRM DELETE</button>
                    <button onClick={()=>setDeleteConfirm(false)} style={{ background:"#333", color:"#aaa", border:"none", padding:"8px 16px", cursor:"pointer", fontFamily:"monospace", fontSize:12 }}>CANCEL</button>
                  </span>
                : <button onClick={()=>setDeleteConfirm(true)} style={{ background:"none", border:"1px solid #444", color:"#666", padding:"8px 16px", cursor:"pointer", fontFamily:"monospace", fontSize:12 }}>
                    ✕ DELETE POLL
                  </button>
            )}
          </div>
          {/* Save / Cancel */}
          <div style={{ display:"flex", gap:10 }}>
            <button onClick={onClose} style={{ background:"#222", color:"#aaa", border:"none", padding:"10px 22px", cursor:"pointer", fontFamily:"monospace", fontSize:12 }}>CANCEL</button>
            <button onClick={handleSave} disabled={!valid} style={{ background:valid?"#1a6bff":"#333", color:valid?"#fff":"#666", border:"none", padding:"10px 28px", cursor:valid?"pointer":"not-allowed", fontFamily:"monospace", fontSize:13, fontWeight:"bold", letterSpacing:"0.08em" }}>
              {isNew ? "ADD POLL" : "SAVE CHANGES"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


// ─── CROSSTABS PANEL ──────────────────────────────────────────────────────────

function CrosstabsPanel({ polls, candidate }) {
  const [activeCategory, setActiveCategory] = useState("gender");
  const pollsWithData = polls.filter(p => p.crosstabs?.[candidate.id]);

  if (pollsWithData.length === 0) return (
    <div style={{ color:"#555", fontFamily:"monospace", fontSize:13, padding:"40px 0" }}>
      No crosstab data available for {candidate.name} in the selected polls.
    </div>
  );

  const latest = [...pollsWithData].sort((a,b) => new Date(b.date)-new Date(a.date))[0];
  const catData = latest?.crosstabs?.[candidate.id]?.[activeCategory];
  const barData = catData ? Object.entries(catData).map(([group,value]) => ({ group, value })) : [];
  const demoGroups = catData ? Object.keys(catData) : [];

  const trendData = [...pollsWithData].sort((a,b) => new Date(a.date)-new Date(b.date)).map(p => {
    const row = { label: `${formatDate(p.date)} (${p.state})`, overall: parseFloat(p[candidate.id]) || null };
    const cd = p.crosstabs?.[candidate.id]?.[activeCategory] || {};
    Object.entries(cd).forEach(([k,v]) => { row[k] = v; });
    return row;
  });

  return (
    <div>
      <div style={{ display:"flex", gap:0, marginBottom:24, borderBottom:"1px solid #222", flexWrap:"wrap" }}>
        {DEMO_CATEGORIES.map(cat => (
          <button key={cat} onClick={()=>setActiveCategory(cat)} style={{
            background:"none", border:"none",
            borderBottom: activeCategory===cat?`2px solid ${candidate.color}`:"2px solid transparent",
            color: activeCategory===cat?"#e8e6df":"#555",
            padding:"8px 16px", cursor:"pointer", fontFamily:"monospace", fontSize:11, letterSpacing:"0.08em", textTransform:"uppercase"
          }}>{DEMO_LABELS[cat]}</button>
        ))}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))", gap:32 }}>
        <div>
          <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.12em", marginBottom:12 }}>
            LATEST SNAPSHOT · {latest ? `${formatDate(latest.date)} · ${latest.pollster} · ${latest.state}` : ""}
          </div>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} layout="vertical" margin={{ left:10, right:30 }}>
                <XAxis type="number" domain={[0,100]} tick={{ fill:"#555", fontSize:10, fontFamily:"monospace" }} tickLine={false} unit="%"/>
                <YAxis type="category" dataKey="group" tick={{ fill:"#aaa", fontSize:11, fontFamily:"monospace" }} tickLine={false} width={95}/>
                <Tooltip contentStyle={{ background:"#111118", border:"1px solid #333", fontFamily:"monospace", fontSize:12 }} formatter={val=>[`${val}%`, candidate.short]}/>
                <Bar dataKey="value" radius={[0,3,3,0]}>
                  {barData.map((_,i) => <Cell key={i} fill={candidate.color} opacity={0.5+(i*0.1)}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div style={{ color:"#444", fontFamily:"monospace", fontSize:12, padding:"20px 0" }}>No data for this category.</div>}
        </div>
        <div>
          <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.12em", marginBottom:12 }}>TREND BY GROUP</div>
          {trendData.length >= 2 && demoGroups.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trendData} margin={{ top:4, right:16, left:0, bottom:4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a22"/>
                  <XAxis dataKey="label" tick={{ fill:"#555", fontSize:9, fontFamily:"monospace" }} tickLine={false}/>
                  <YAxis tick={{ fill:"#555", fontSize:10, fontFamily:"monospace" }} tickLine={false} unit="%" domain={[0,"auto"]}/>
                  <Tooltip contentStyle={{ background:"#111118", border:"1px solid #333", fontFamily:"monospace", fontSize:11 }} formatter={(v,n)=>[`${v}%`,n]}/>
                  {demoGroups.map((g,i) => <Line key={g} type="monotone" dataKey={g} stroke={GROUP_COLORS[i%GROUP_COLORS.length]} strokeWidth={2} dot={{ r:3 }} connectNulls/>)}
                </LineChart>
              </ResponsiveContainer>
              <div style={{ display:"flex", gap:12, flexWrap:"wrap", marginTop:8 }}>
                {demoGroups.map((g,i) => <span key={g} style={{ fontSize:10, fontFamily:"monospace", color:GROUP_COLORS[i%GROUP_COLORS.length] }}>● {g}</span>)}
              </div>
            </>
          ) : <div style={{ color:"#444", fontFamily:"monospace", fontSize:12, padding:"20px 0" }}>Need 2+ polls with crosstab data.</div>}
        </div>
      </div>
      <div style={{ marginTop:28 }}>
        <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.12em", marginBottom:12 }}>RAW CROSSTAB DATA</div>
        <div style={{ overflowX:"auto" }}>
          <table style={{ borderCollapse:"collapse", fontFamily:"monospace", fontSize:12, width:"100%" }}>
            <thead>
              <tr>
                <th style={thStyle}>Poll</th><th style={thStyle}>State</th><th style={thStyle}>Date</th>
                <th style={{ ...thStyle, color:candidate.color }}>Overall</th>
                {demoGroups.map(g => <th key={g} style={thStyle}>{g}</th>)}
              </tr>
            </thead>
            <tbody>
              {[...pollsWithData].sort((a,b)=>new Date(b.date)-new Date(a.date)).map(p => {
                const ct = p.crosstabs[candidate.id][activeCategory] || {};
                return (
                  <tr key={p.id} style={{ borderBottom:"1px solid #1a1a22" }}>
                    <td style={tdStyle}>{p.pollster}</td>
                    <td style={{ ...tdStyle, color: p.state==="National"?"#888":"#e9c46a" }}>{p.state}</td>
                    <td style={{ ...tdStyle, color:"#888" }}>{formatDate(p.date)}</td>
                    <td style={{ ...tdStyle, color:candidate.color, fontWeight:"bold" }}>{p[candidate.id]}%</td>
                    {demoGroups.map(g => <td key={g} style={tdStyle}>{ct[g]!=null?`${ct[g]}%`:"—"}</td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


// ─── PASSWORD GATE ────────────────────────────────────────────────────────────

function PasswordGate({ children }) {
  const [input, setInput] = useState("");
  const [authed, setAuthed] = useState(() => { try { return sessionStorage.getItem("auth") === "yes"; } catch { return false; } });
  const [error, setError] = useState(false);
  function attempt() {
    if (input === "tree81x") { sessionStorage.setItem("auth","yes"); setAuthed(true); }
    else { setError(true); setTimeout(()=>setError(false),1500); }
  }
  if (authed) return children;
  return (
    <div style={{background:"#0a0a0f",minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",fontFamily:"monospace"}}>
      <div style={{textAlign:"center",padding:40}}>
        <div style={{fontSize:11,letterSpacing:"0.2em",color:"#1a6bff",marginBottom:8}}>2028 DEMOCRATIC PRIMARY</div>
        <div style={{fontSize:28,fontWeight:"bold",color:"#e8e6df",marginBottom:32,fontFamily:"Georgia,serif"}}>Polling Tracker</div>
        <div style={{marginBottom:16}}>
          <input type="password" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&attempt()} placeholder="Enter password" autoFocus style={{background:"#111118",border:`1px solid ${error?"#e63946":"#444"}`,color:"#e8e6df",padding:"12px 18px",fontFamily:"monospace",fontSize:14,outline:"none",width:220,textAlign:"center"}}/>
        </div>
        <button onClick={attempt} style={{background:"#1a6bff",color:"#fff",border:"none",padding:"10px 32px",cursor:"pointer",fontFamily:"monospace",fontSize:13,fontWeight:"bold",letterSpacing:"0.1em"}}>ENTER</button>
        {error && <div style={{color:"#e63946",fontSize:12,marginTop:14,letterSpacing:"0.05em"}}>Incorrect password</div>}
      </div>
    </div>
  );
}


// ─── MAIN APP ─────────────────────────────────────────────────────────────────

export default function PollingTracker() {
  const [basePollsFromServer, setBasePollsFromServer] = useState([]);
  const [delta, setDelta]                             = useState({ edits:{}, additions:[], deletions:[] });
  const [loaded, setLoaded]                           = useState(false);
  const [lastUpdated, setLastUpdated]                 = useState(null);
  const [activeTab, setActiveTab]                     = useState("chart");
  const [visibleCands, setVisibleCands]               = useState(CANDIDATES.map(c=>c.id));
  const [crosstabCandidate, setCrosstabCandidate]     = useState("harris");
  const [stateFilter, setStateFilter]                 = useState("All");
  const [demoFilter, setDemoFilter]                   = useState(null);
  const [editingPoll, setEditingPoll]                 = useState(null); // null = closed, poll obj = open

  // Load server polls + local delta
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/polls.json?t=" + Date.now());
        const data = await res.json();
        setBasePollsFromServer(data);
        setLastUpdated(new Date().toLocaleDateString());
      } catch { setBasePollsFromServer([]); }
      setDelta(loadDelta());
      setLoaded(true);
    }
    load();
  }, []);

  // Persist delta whenever it changes
  useEffect(() => {
    if (loaded) saveDelta(delta);
  }, [delta, loaded]);

  // Compute all polls: base - deletions + edits applied + additions
  const allPolls = useMemo(() => {
    const polls = basePollsFromServer
      .filter(p => !delta.deletions.includes(p.id))
      .map(p => delta.edits[p.id] ? { ...p, ...delta.edits[p.id] } : p);
    return [...polls, ...delta.additions].sort((a,b) => new Date(a.date) - new Date(b.date));
  }, [basePollsFromServer, delta]);

  const localChangeCount = Object.keys(delta.edits).length + delta.additions.length + delta.deletions.length;

  const allStates = useMemo(() => {
    const states = [...new Set(allPolls.map(p => p.state || "National"))].sort();
    return ["All", "National", ...states.filter(s => s !== "National")];
  }, [allPolls]);

  const filteredPolls = useMemo(() =>
    stateFilter === "All" ? allPolls : allPolls.filter(p => (p.state || "National") === stateFilter),
  [allPolls, stateFilter]);

  // ── Edit / Add / Delete handlers ──

  function openAddModal() {
    setEditingPoll({ id:"__new__" });
  }

  function openEditModal(poll) {
    setEditingPoll(poll);
  }

  function handleSavePoll(saved) {
    if (saved.id === "__new__") {
      // New poll addition
      const newPoll = { ...saved, id: `manual-${Date.now()}` };
      setDelta(d => ({ ...d, additions: [...d.additions, newPoll] }));
    } else {
      // Edit existing poll — store delta
      const { id, ...fields } = saved;
      setDelta(d => ({ ...d, edits: { ...d.edits, [id]: fields } }));
    }
    setEditingPoll(null);
  }

  function handleDeletePoll(pollId) {
    if (pollId.startsWith("manual-")) {
      // Remove from additions
      setDelta(d => ({ ...d, additions: d.additions.filter(p => p.id !== pollId) }));
    } else {
      // Add to deletions (hides from server polls)
      setDelta(d => ({
        ...d,
        deletions: [...d.deletions, pollId],
        edits: Object.fromEntries(Object.entries(d.edits).filter(([k]) => k !== pollId))
      }));
    }
    setEditingPoll(null);
  }

  function resetLocalChanges() {
    if (!window.confirm("Reset all local edits, additions, and deletions? Server data will be restored.")) return;
    const empty = { edits:{}, additions:[], deletions:[] };
    setDelta(empty);
    saveDelta(empty);
  }

  function exportPollsJson() {
    const sorted = [...allPolls].sort((a,b) => new Date(b.date) - new Date(a.date));
    const blob = new Blob([JSON.stringify(sorted, null, 2)], { type:"application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "polls.json"; a.click();
    URL.revokeObjectURL(url);
  }

  // ── Derived data ──

  const averages = useMemo(() =>
    CANDIDATES.map(c => ({ ...c, avg: weightedAverageDemo(filteredPolls, c.id, demoFilter) }))
      .filter(c => c.avg !== null)
      .sort((a,b) => parseFloat(b.avg) - parseFloat(a.avg)),
  [filteredPolls, demoFilter]);

  const chartData = useMemo(() =>
    [...filteredPolls].sort((a,b) => new Date(a.date) - new Date(b.date)).map(p => {
      const row = { label:`${formatDate(p.date)}${p.state&&p.state!=="National"?` (${p.state})`:""}`, pollster:p.pollster, state:p.state };
      CANDIDATES.forEach(c => { row[c.id] = parseFloat(p[c.id]) || null; });
      return row;
    }),
  [filteredPolls]);

  const selectedCrosstabCand = CANDIDATES.find(c=>c.id===crosstabCandidate) || CANDIDATES[0];
  const nationalCount = allPolls.filter(p=>(p.state||"National")==="National").length;
  const stateCount = allPolls.filter(p=>p.state&&p.state!=="National").length;

  if (!loaded) return (
    <div style={{ background:"#0a0a0f", minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", color:"#fff", fontFamily:"Georgia,serif", fontSize:18 }}>
      Loading tracker...
    </div>
  );

  return (
    <PasswordGate>
    <div style={{ background:"#0a0a0f", minHeight:"100vh", color:"#e8e6df", fontFamily:"'Georgia','Times New Roman',serif" }}>

      {/* Edit Modal */}
      {editingPoll && (
        <PollEditModal
          poll={editingPoll}
          onSave={handleSavePoll}
          onDelete={() => handleDeletePoll(editingPoll.id)}
          onClose={() => setEditingPoll(null)}
        />
      )}

      {/* Header */}
      <div style={{ borderBottom:"3px solid #1a6bff", padding:"28px 36px 18px" }}>
        <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", flexWrap:"wrap", gap:12 }}>
          <div>
            <div style={{ fontSize:11, letterSpacing:"0.2em", textTransform:"uppercase", color:"#1a6bff", fontFamily:"monospace", marginBottom:4 }}>2028 Presidential Primary</div>
            <h1 style={{ margin:0, fontSize:"clamp(22px,4vw,36px)", fontWeight:"bold", letterSpacing:"-0.02em", lineHeight:1.1 }}>
              Democratic Primary<br/><span style={{ color:"#1a6bff" }}>Polling Tracker</span>
            </h1>
          </div>
          <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
            {localChangeCount > 0 && (
              <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                <span style={{ fontSize:11, color:"#e9c46a", fontFamily:"monospace", background:"#e9c46a18", border:"1px solid #e9c46a44", padding:"4px 10px" }}>
                  {localChangeCount} local edit{localChangeCount!==1?"s":""}
                </span>
                <button onClick={exportPollsJson} style={{ background:"#1a6bff22", border:"1px solid #1a6bff66", color:"#1a6bff", padding:"6px 14px", cursor:"pointer", fontFamily:"monospace", fontSize:11, letterSpacing:"0.05em" }}>
                  ↓ EXPORT polls.json
                </button>
                <button onClick={resetLocalChanges} style={{ background:"none", border:"1px solid #444", color:"#666", padding:"6px 14px", cursor:"pointer", fontFamily:"monospace", fontSize:11 }}>
                  RESET
                </button>
              </div>
            )}
            <button onClick={openAddModal} style={{ background:"#1a6bff", color:"#fff", border:"none", padding:"10px 20px", cursor:"pointer", fontFamily:"monospace", fontSize:13, letterSpacing:"0.05em", fontWeight:"bold" }}>
              + ADD POLL
            </button>
          </div>
        </div>
        <div style={{ marginTop:10, fontSize:12, color:"#888", fontFamily:"monospace", display:"flex", gap:24, flexWrap:"wrap" }}>
          <span>{nationalCount} national · {stateCount} state polls · Apr 2025–present</span>
          <span style={{ color:"#2a9d8f" }}>⟳ Auto-updated daily via GitHub Actions</span>
          {lastUpdated && <span>Last loaded: {lastUpdated}</span>}
        </div>
      </div>

      {/* State Filter */}
      <div style={{ padding:"20px 36px 0", overflowX:"auto" }}>
        <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.15em", marginBottom:10 }}>FILTER BY STATE / GEOGRAPHY</div>
        <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
          {allStates.map(s => (
            <button key={s} onClick={()=>setStateFilter(s)} style={{
              background: stateFilter===s?"#1a6bff":"#111118",
              border:`1px solid ${stateFilter===s?"#1a6bff":"#333"}`,
              color: stateFilter===s?"#fff":"#888",
              padding:"5px 14px", cursor:"pointer", fontFamily:"monospace", fontSize:11,
              letterSpacing:"0.05em", whiteSpace:"nowrap"
            }}>{s}</button>
          ))}
        </div>
      </div>

      {/* Demographic Filter */}
      <div style={{ padding:"16px 36px 0", overflowX:"auto" }}>
        <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.15em", marginBottom:10 }}>FILTER BY DEMOGRAPHIC</div>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          <div style={{ display:"flex", gap:8, flexWrap:"wrap", alignItems:"center" }}>
            <button onClick={()=>setDemoFilter(null)} style={{
              background: demoFilter===null?"#1a6bff":"#111118",
              border:`1px solid ${demoFilter===null?"#1a6bff":"#333"}`,
              color: demoFilter===null?"#fff":"#888",
              padding:"5px 14px", cursor:"pointer", fontFamily:"monospace", fontSize:11, letterSpacing:"0.05em", whiteSpace:"nowrap"
            }}>Overall</button>
          </div>
          {Object.keys(DEMO_CATEGORY_LABELS).map(cat => (
            <div key={cat} style={{ display:"flex", gap:6, flexWrap:"wrap", alignItems:"center" }}>
              <span style={{ fontSize:9, color:"#555", fontFamily:"monospace", letterSpacing:"0.12em", minWidth:72 }}>{DEMO_CATEGORY_LABELS[cat]}</span>
              {DEMO_FILTERS.filter(d=>d.category===cat).map(d => {
                const isActive = demoFilter?.category===d.category && demoFilter?.group===d.group;
                return (
                  <button key={d.group} onClick={()=>setDemoFilter(isActive?null:d)} style={{
                    background: isActive?"#2a9d8f22":"#111118",
                    border:`1px solid ${isActive?"#2a9d8f":"#333"}`,
                    color: isActive?"#2a9d8f":"#888",
                    padding:"5px 14px", cursor:"pointer", fontFamily:"monospace", fontSize:11, letterSpacing:"0.05em", whiteSpace:"nowrap"
                  }}>{d.group}</button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Averages */}
      <div style={{ padding:"20px 36px 0", overflowX:"auto" }}>
        <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.15em", marginBottom:14 }}>
          WEIGHTED POLLING AVERAGE {stateFilter!=="All"?`· ${stateFilter} only`:""}{demoFilter?` · ${demoFilter.group} voters`:""} · click to toggle on chart
        </div>
        <div style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
          {averages.map((c,i) => (
            <div key={c.id} onClick={()=>setVisibleCands(prev=>prev.includes(c.id)?prev.filter(x=>x!==c.id):[...prev,c.id])}
              style={{ background:i===0?`${c.color}20`:"#111118", border:`1px solid ${i===0?c.color:"#222"}`, padding:"14px 18px", minWidth:110, cursor:"pointer", opacity:visibleCands.includes(c.id)?1:0.35, transition:"all 0.15s" }}>
              <div style={{ fontSize:10, color:c.color, fontFamily:"monospace", letterSpacing:"0.1em", marginBottom:4 }}>{i===0?"● LEADER":`#${i+1}`}</div>
              <div style={{ fontSize:24, fontWeight:"bold", color:c.color, lineHeight:1 }}>{c.avg}%</div>
              <div style={{ fontSize:12, color:"#aaa", marginTop:4 }}>{c.short}</div>
            </div>
          ))}
          {averages.length === 0 && <div style={{ color:"#555", fontFamily:"monospace", fontSize:13 }}>No polls for this state yet.</div>}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding:"24px 36px 0", display:"flex", gap:0, borderBottom:"1px solid #222", marginTop:24 }}>
        {["chart","table","crosstabs"].map(tab=>(
          <button key={tab} onClick={()=>setActiveTab(tab)} style={{ background:"none", border:"none", borderBottom:activeTab===tab?"2px solid #1a6bff":"2px solid transparent", color:activeTab===tab?"#e8e6df":"#666", padding:"8px 20px", cursor:"pointer", fontFamily:"monospace", fontSize:12, letterSpacing:"0.1em", textTransform:"uppercase" }}>
            {tab}
          </button>
        ))}
      </div>

      {/* Chart */}
      {activeTab==="chart" && (
        <div style={{ padding:"24px 36px" }}>
          <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.15em", marginBottom:6 }}>
            POLLING TRENDS · {stateFilter==="All"?"All polls":stateFilter} · Apr 2025–present
          </div>
          {chartData.length < 2
            ? <div style={{ color:"#555", fontFamily:"monospace", fontSize:13, padding:"40px 0" }}>Need at least 2 polls for this view. Try selecting "All" above.</div>
            : <ResponsiveContainer width="100%" height={400}>
                <LineChart data={chartData} margin={{ top:10, right:20, left:0, bottom:10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a22"/>
                  <XAxis dataKey="label" tick={{ fill:"#666", fontSize:10, fontFamily:"monospace" }} tickLine={false}/>
                  <YAxis tick={{ fill:"#666", fontSize:11, fontFamily:"monospace" }} tickLine={false} unit="%" domain={[0,"auto"]}/>
                  <Tooltip contentStyle={{ background:"#111118", border:"1px solid #333", fontFamily:"monospace", fontSize:12 }} labelStyle={{ color:"#aaa", marginBottom:6 }} formatter={(val,name)=>{ const c=CANDIDATES.find(c=>c.id===name); return [`${val}%`,c?.short||name]; }}/>
                  {CANDIDATES.filter(c=>visibleCands.includes(c.id)).map(c=>(
                    <Line key={c.id} type="monotone" dataKey={c.id} stroke={c.color} strokeWidth={2} dot={{ r:4, fill:c.color, strokeWidth:0 }} connectNulls activeDot={{ r:6 }}/>
                  ))}
                </LineChart>
              </ResponsiveContainer>
          }
        </div>
      )}

      {/* Table */}
      {activeTab==="table" && (
        <div style={{ padding:"24px 36px", overflowX:"auto" }}>
          <table style={{ borderCollapse:"collapse", width:"100%", fontFamily:"monospace", fontSize:12 }}>
            <thead>
              <tr>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Pollster</th>
                <th style={{ ...thStyle, color:"#e9c46a" }}>State</th>
                <th style={thStyle}>N</th>
                {CANDIDATES.map(c=><th key={c.id} style={{ ...thStyle, color:c.color }}>{c.short}</th>)}
                <th style={thStyle}>Crosstabs</th>
                <th style={{ ...thStyle, width:40 }}></th>
              </tr>
            </thead>
            <tbody>
              {[...filteredPolls].sort((a,b)=>new Date(b.date)-new Date(a.date)).map(p=>{
                const isManual = p.id?.startsWith("manual-");
                const isEdited = !!delta.edits[p.id];
                const hasCrosstabs = !!p.crosstabs;
                const isState = p.state && p.state !== "National";
                return (
                  <tr key={p.id} style={{ borderBottom:"1px solid #1a1a22" }}>
                    <td style={tdStyle}>{formatDate(p.date)}</td>
                    <td style={tdStyle}>
                      {p.pollster}
                      {isManual && <span style={{ fontSize:9, color:"#555", marginLeft:6 }}>manual</span>}
                      {isEdited && <span style={{ fontSize:9, color:"#e9c46a", marginLeft:6 }}>edited</span>}
                    </td>
                    <td style={{ ...tdStyle, color: isState?"#e9c46a":"#666" }}>{p.state||"National"}</td>
                    <td style={{ ...tdStyle, color:"#666" }}>{p.sampleSize?Number(p.sampleSize).toLocaleString():"—"}</td>
                    {CANDIDATES.map(c=>{
                      const val = getDemoValue(p, c.id, demoFilter);
                      const isLeader = val!==null&&!isNaN(val)&&CANDIDATES.every(o=>o.id===c.id||getDemoValue(p,o.id,demoFilter)===null||getDemoValue(p,o.id,demoFilter)<=val);
                      return <td key={c.id} style={{ ...tdStyle, color:val!==null&&!isNaN(val)?(isLeader?c.color:"#e8e6df"):"#333", fontWeight:isLeader?"bold":"normal" }}>{val!==null&&!isNaN(val)?`${val}%`:"—"}</td>;
                    })}
                    <td style={tdStyle}>
                      {hasCrosstabs
                        ? <span style={{ color:"#2a9d8f", fontSize:11, cursor:"pointer" }} onClick={()=>setActiveTab("crosstabs")}>✓ view</span>
                        : <span style={{ color:"#333", fontSize:11 }}>—</span>}
                    </td>
                    <td style={{ ...tdStyle, textAlign:"center" }}>
                      <button onClick={()=>openEditModal(p)} style={{ background:"none", border:"1px solid #333", color:"#555", cursor:"pointer", fontSize:11, padding:"3px 8px", fontFamily:"monospace" }} title="Edit poll">
                        ✎
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr style={{ borderTop:"2px solid #333" }}>
                <td colSpan={4} style={{ ...tdStyle, color:"#1a6bff", letterSpacing:"0.1em" }}>AVG {stateFilter!=="All"?`(${stateFilter})`:""}</td>
                {CANDIDATES.map(c=><td key={c.id} style={{ ...tdStyle, color:c.color, fontWeight:"bold" }}>{weightedAverageDemo(filteredPolls,c.id,demoFilter)?`${weightedAverageDemo(filteredPolls,c.id,demoFilter)}%`:"—"}</td>)}
                <td colSpan={2} style={tdStyle}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Crosstabs */}
      {activeTab==="crosstabs" && (
        <div style={{ padding:"24px 36px" }}>
          <div style={{ fontSize:11, color:"#666", fontFamily:"monospace", letterSpacing:"0.15em", marginBottom:16 }}>
            DEMOGRAPHIC CROSSTABS · {stateFilter==="All"?"All polls":stateFilter} · select a candidate
          </div>
          <div style={{ display:"flex", gap:10, flexWrap:"wrap", marginBottom:28 }}>
            {CANDIDATES.map(c => {
              const hasCT = filteredPolls.some(p=>p.crosstabs?.[c.id]);
              return (
                <button key={c.id} onClick={()=>hasCT&&setCrosstabCandidate(c.id)} style={{
                  background:crosstabCandidate===c.id?`${c.color}25`:"#111118",
                  border:`1px solid ${crosstabCandidate===c.id?c.color:"#333"}`,
                  color:hasCT?c.color:"#444",
                  padding:"8px 16px", cursor:hasCT?"pointer":"default",
                  fontFamily:"monospace", fontSize:12, letterSpacing:"0.05em", opacity:hasCT?1:0.4,
                }}>
                  {c.short}{hasCT&&<span style={{ fontSize:9, marginLeft:6, opacity:0.7 }}>● data</span>}
                </button>
              );
            })}
          </div>
          <div style={{ marginBottom:20, paddingBottom:16, borderBottom:"1px solid #1a1a22" }}>
            <span style={{ fontSize:22, fontWeight:"bold", color:selectedCrosstabCand.color }}>{selectedCrosstabCand.name}</span>
            <span style={{ fontSize:13, color:"#666", fontFamily:"monospace", marginLeft:16 }}>
              avg {weightedAverage(filteredPolls, selectedCrosstabCand.id) || "—"}% · {stateFilter==="All"?"all polls":stateFilter}
            </span>
          </div>
          <CrosstabsPanel polls={filteredPolls} candidate={selectedCrosstabCand}/>
        </div>
      )}

      <div style={{ padding:"16px 36px 32px", borderTop:"1px solid #1a1a22", marginTop:8 }}>
        <div style={{ fontSize:11, color:"#444", fontFamily:"monospace" }}>
          Polls tracked from Apr 1, 2025 · National + state-level polls · Auto-fetched daily via GitHub Actions + Anthropic API · Weighted by recency × sample size · No candidates formally declared as of Feb 2026
        </div>
      </div>
    </div>
    </PasswordGate>
  );
}
