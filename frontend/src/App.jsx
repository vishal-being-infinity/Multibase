import { useState, useRef, useEffect } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";
import "./App.css";

const API_URL = "http://localhost:8000";
const PALETTE = ["#3fb950", "#4c8bf5", "#d4a72c", "#f85149", "#a78bfa", "#5fb0e8", "#e88b4f", "#6bc9c9"];
const LEGEND_LIMIT = 12;

const SUGGESTIONS = [
  { text: "which students solved the most hard problems?", hint: "aggregate" },
  { text: "average submission runtime by language", hint: "compare" },
  { text: "submissions per day this month", hint: "trend" },
];

function colorAt(i) { return PALETTE[i % PALETTE.length]; }

function Verdict({ status }) {
  const map = {
    ok: { label: "AC", cls: "verdict-ac" },
    ambiguous: { label: "?", cls: "verdict-pending" },
    error: { label: "CE", cls: "verdict-ce" },
  };
  const v = map[status];
  return <span className={`verdict ${v.cls}`}>{v.label}</span>;
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{label ?? payload[0].name}</div>
      <div className="chart-tooltip-value">{payload[0].value}</div>
    </div>
  );
}

// color swatch + label + value per data point; caps at LEGEND_LIMIT with a "+N more" note
function ChartLegend({ rows, labelCol, numericCol }) {
  const shown = rows.slice(0, LEGEND_LIMIT);
  const remaining = rows.length - shown.length;
  return (
    <div className="chart-legend">
      {shown.map((r, i) => (
        <div className="legend-item" key={i}>
          <span className="legend-swatch" style={{ background: colorAt(i) }} />
          <span className="legend-label">{String(r[labelCol])}</span>
          <span className="legend-value">{r[numericCol]}</span>
        </div>
      ))}
      {remaining > 0 && <div className="legend-more">+{remaining} more</div>}
    </div>
  );
}

// looks at column names/values to decide: line (trend), pie (small breakdown),
// horizontal bar (long labels / many rows), vertical bar (default), or table
function decideView(rows) {
  const columns = Object.keys(rows[0]);
  const isIdLike = (c) => c === "id" || c.endsWith("_id");
  const numericCols = columns.filter((c) => typeof rows[0][c] === "number" && !isIdLike(c));
  const labelCol = columns.find((c) => !isIdLike(c) && !numericCols.includes(c));

  if (numericCols.length !== 1 || !labelCol || rows.length > 30) {
    return { type: "table", labelCol, numericCol: null };
  }
  const numericCol = numericCols[0];
  const isDateLike = /date|time|day|week|month|year/i.test(labelCol);
  const avgLabelLen = rows.reduce((sum, r) => sum + String(r[labelCol]).length, 0) / rows.length;

  if (isDateLike && rows.length > 3) return { type: "line", labelCol, numericCol };
  if (rows.length <= 6) return { type: "pie", labelCol, numericCol };
  if (avgLabelLen > 12 || rows.length > 10) return { type: "hbar", labelCol, numericCol };
  return { type: "bar", labelCol, numericCol };
}

function TableView({ rows }) {
  const columns = Object.keys(rows[0]);
  return (
    <div className="table-wrap">
      <table className="scoreboard">
        <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>{columns.map((c) => <td key={c}>{String(row[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartView({ type, rows, labelCol, numericCol }) {
  if (type === "line") {
    return (
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#1a1f2b" vertical={false} />
          <XAxis dataKey={labelCol} tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={{ stroke: "#232937" }} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Line type="monotone" dataKey={numericCol} stroke="#4c8bf5" strokeWidth={2} dot={{ r: 3, fill: "#4c8bf5" }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }
  if (type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Tooltip content={<ChartTooltip />} />
          <Pie data={rows} dataKey={numericCol} nameKey={labelCol} innerRadius={50} outerRadius={80} paddingAngle={2} isAnimationActive={false}>
            {rows.map((_, i) => <Cell key={i} fill={colorAt(i)} stroke="var(--bg-panel)" strokeWidth={2} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    );
  }
  if (type === "hbar") {
    return (
      <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 28)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
          <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={{ stroke: "#232937" }} tickLine={false} />
          <YAxis type="category" dataKey={labelCol} tick={{ fontSize: 10, fill: "#6B7280" }} width={110} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(76,139,245,0.06)" }} />
          <Bar dataKey={numericCol} radius={[0, 3, 3, 0]} isAnimationActive={false}>
            {rows.map((_, i) => <Cell key={i} fill={colorAt(i)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <XAxis dataKey={labelCol} tick={{ fontSize: 10, fill: "#6B7280" }} interval={0} angle={-25} textAnchor="end" height={55} axisLine={{ stroke: "#232937" }} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={false} tickLine={false} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(76,139,245,0.06)" }} />
        <Bar dataKey={numericCol} radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {rows.map((_, i) => <Cell key={i} fill={colorAt(i)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ResultsView({ rows }) {
  const detected = rows?.length ? decideView(rows) : { type: "table" };
  const [view, setView] = useState(detected.type); // chart-vs-table toggle state, kept regardless of which view renders
  const { labelCol, numericCol } = detected;

  if (!rows?.length) return <p className="empty">no rows returned</p>;

  const showToggle = detected.type !== "table";

  return (
    <div>
      {showToggle && (
        <div className="view-toggle">
          <button className={view === detected.type ? "active" : ""} onClick={() => setView(detected.type)}>chart</button>
          <button className={view === "table" ? "active" : ""} onClick={() => setView("table")}>table</button>
        </div>
      )}

      {view === "table" ? (
        <TableView rows={rows} />
      ) : (
        <>
          <ChartView type={view} rows={rows} labelCol={labelCol} numericCol={numericCol} />
          <ChartLegend rows={rows} labelCol={labelCol} numericCol={numericCol} />
        </>
      )}
    </div>
  );
}

function SqlPanel({ sql }) {
  const [open, setOpen] = useState(true); // open by default
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable, silently ignore */
    }
  }

  // Always the same node, only the "collapsed" class ever toggles - this is
  // what lets the width transition run smoothly instead of jumping.
  return (
    <div className={`sql-panel-inline${open ? "" : " collapsed"}`}>
      {open ? (
        <>
          <div className="sql-panel-head">
            <span className="sql-panel-label">query</span>
            <div className="sql-panel-actions">
              <button className={`sql-action${copied ? " copied" : ""}`} onClick={handleCopy}>
                {copied ? "copied" : "copy"}
              </button>
              <button className="sql-action" onClick={() => setOpen(false)} aria-label="collapse query" aria-expanded="true">
                &raquo;
              </button>
            </div>
          </div>
          <pre className="sql">{sql}</pre>
        </>
      ) : (
        <button className="sql-panel-toggle-collapsed" onClick={() => setOpen(true)} aria-label="show query" aria-expanded="false">
          <span className="sql-strip-label">query</span>
        </button>
      )}
    </div>
  );
}

function ResultCard({ msg }) {
  return (
    <div className={`card card-${msg.status}`}>
      <div className="card-head">
        <Verdict status={msg.status} />
        {msg.ms != null && <span className="ms">{msg.ms}ms</span>}
      </div>

      {msg.text && <p className="card-text">{msg.text}</p>}

      {msg.rows && (
        <div className="card-body">
          <div className="card-main">
            <ResultsView rows={msg.rows} />
          </div>
          {msg.sql && <SqlPanel sql={msg.sql} />}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const transcriptRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  async function submitQuestion(text) {
    if (!text.trim() || loading) return;

    const userTurn = { role: "user", content: text };
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    setQuestion("");
    const startedAt = performance.now();

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, history }),
      });
      const data = await res.json();
      const elapsedMs = Math.round(performance.now() - startedAt);

      if (data.status === "ambiguous") {
        setHistory((prev) => [...prev, userTurn, { role: "assistant", content: data.clarifying_question }]);
        setMessages((prev) => [...prev, { role: "assistant", status: "ambiguous", text: data.clarifying_question, ms: elapsedMs }]);
      } else if (data.status === "ok") {
        setHistory([]);
        setMessages((prev) => [...prev, { role: "assistant", status: "ok", sql: data.sql, rows: data.rows, ms: elapsedMs }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", status: "error", text: data.detail || "query failed", ms: elapsedMs }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", status: "error", text: err.message }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleAsk(e) {
    e.preventDefault();
    submitQuestion(question);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <span className="dot" />
          <span className="brand">nl2sql</span>
          <span className="brand-sub">competitive programming judge</span>
        </div>
        <span className="topbar-right">postgres · claude</span>
      </header>

      <main className="transcript" ref={transcriptRef}>
        {messages.length === 0 && (
          <div className="empty-state">
            <p className="empty-title">no submissions yet</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.text}
                  type="button"
                  className="suggestion-chip"
                  onClick={() => submitQuestion(s.text)}
                >
                  <span>{s.text}</span>
                  <span className="suggestion-hint">{s.hint}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="line user-line">
              <span className="prompt-glyph">&gt;</span>
              <span>{m.text}</span>
            </div>
          ) : (
            <ResultCard key={i} msg={m} />
          )
        )}

        {loading && (
          <div className="line pending-line">
            <span className="prompt-glyph dim">&gt;</span>
            <span className="thinking">judging<span className="dots" /></span>
          </div>
        )}
      </main>

      <form onSubmit={handleAsk} className="input-bar">
        <span className="prompt-glyph">&gt;</span>
        <input
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="ask a question about students, contests, or submissions"
          aria-label="Ask a question"
          autoFocus
        />
        <button type="submit" disabled={loading || !question.trim()}>submit</button>
      </form>
    </div>
  );
}
