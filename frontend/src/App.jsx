import { useState, useRef, useEffect, useLayoutEffect, createContext, useContext } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from "recharts";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PALETTE = ["#3fb950", "#4c8bf5", "#d4a72c", "#f85149", "#a78bfa", "#5fb0e8", "#e88b4f", "#6bc9c9"];
const LEGEND_LIMIT = 12;
const THEME_KEY = "multibase-theme";
const HISTORY_KEY = "multibase-chat";
const HISTORY_TTL_MS = 24 * 60 * 60 * 1000; // rolling 24h - refreshed on every new message

// recharts wants real color strings (not CSS var()) for SVG props, so each
// theme gets its own small lookup instead of relying on var() in inline SVG attrs.
const CHART_THEME = {
  dark: { grid: "#1a1f2b", axisLine: "#232937", tick: "#6b7280", line: "#4c8bf5", cursor: "rgba(76, 139, 245, 0.06)" },
  light: { grid: "#e4e7ec", axisLine: "#d7dbe3", tick: "#6b7280", line: "#1f6feb", cursor: "rgba(31, 111, 235, 0.07)" },
};

const SUGGESTIONS = [
  { text: "which students solved the most hard problems?", hint: "aggregate" },
  { text: "average submission runtime by language", hint: "compare" },
  { text: "submissions per day this month", hint: "trend" },
];

const ThemeContext = createContext("dark");

function getInitialTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* localStorage unavailable, fall through to system preference */
  }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

// restores the saved transcript if it's still within its rolling 24h window,
// otherwise drops whatever's stored so a stale chat never resurfaces silently
function loadStoredMessages() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const { messages, savedAt } = JSON.parse(raw);
    if (!Array.isArray(messages) || typeof savedAt !== "number") return [];
    if (Date.now() - savedAt > HISTORY_TTL_MS) {
      localStorage.removeItem(HISTORY_KEY);
      return [];
    }
    return messages;
  } catch {
    return [];
  }
}

function colorAt(i) { return PALETTE[i % PALETTE.length]; }
function humanize(col) { return String(col).replace(/_/g, " "); }
function fmtNum(n) {
  if (typeof n !== "number" || Number.isNaN(n)) return n;
  const rounded = Math.round(n * 100) / 100;
  return rounded.toLocaleString();
}

// small inline icons for the theme toggle knob - real SVGs rather than unicode
// glyphs so sun/moon render identically (and legibly) across every platform
function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2.5M12 19v2.5M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2.5 12H5M19 12h2.5M4.2 19.8L6 18M18 6l1.8-1.8" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor" stroke="none">
      <path d="M20.5 14.5a8.5 8.5 0 1 1-9-11 7 7 0 0 0 9 11z" />
    </svg>
  );
}
function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13M10 11v6M14 11v6" />
    </svg>
  );
}

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
  const p = payload[0];
  const key = p.dataKey || p.name;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-label">{label ?? p.name}</div>
      <div className="chart-tooltip-value">
        {fmtNum(p.value)}
        {key && <span className="chart-tooltip-key">{humanize(key)}</span>}
      </div>
    </div>
  );
}

// title + row/total/average context sitting above the chart itself
function ChartHeader({ rows, labelCol, numericCol, type }) {
  const total = rows.reduce((sum, r) => sum + (Number(r[numericCol]) || 0), 0);
  const avg = rows.length ? total / rows.length : 0;
  return (
    <div className="chart-header">
      <span className="chart-title">{humanize(numericCol)} by {humanize(labelCol)}</span>
      <span className="chart-stats">
        {rows.length} {rows.length === 1 ? "row" : "rows"}
        {type !== "line" && <> · total {fmtNum(total)}</>}
        {" "}· avg {fmtNum(avg)}
      </span>
    </div>
  );
}

// color swatch + label + value + share-of-total per data point; caps at LEGEND_LIMIT with a "+N more" note
function ChartLegend({ rows, labelCol, numericCol, total }) {
  const shown = rows.slice(0, LEGEND_LIMIT);
  const remaining = rows.length - shown.length;
  return (
    <div className="chart-legend">
      {shown.map((r, i) => {
        const value = Number(r[numericCol]) || 0;
        const pct = total ? Math.round((value / total) * 100) : null;
        return (
          <div className="legend-item" key={i}>
            <span className="legend-swatch" style={{ background: colorAt(i) }} />
            <span className="legend-label">{String(r[labelCol])}</span>
            <span className="legend-value">
              {fmtNum(value)}
              {pct != null && <span className="legend-pct">{pct}%</span>}
            </span>
          </div>
        );
      })}
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
  const theme = useContext(ThemeContext);
  const c = CHART_THEME[theme];

  if (type === "line") {
    return (
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis dataKey={labelCol} tick={{ fontSize: 10, fill: c.tick }} axisLine={{ stroke: c.axisLine }} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: c.tick }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Line type="monotone" dataKey={numericCol} stroke={c.line} strokeWidth={2} dot={{ r: 3, fill: c.line }} isAnimationActive={false} />
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
          <XAxis type="number" tick={{ fontSize: 10, fill: c.tick }} axisLine={{ stroke: c.axisLine }} tickLine={false} />
          <YAxis type="category" dataKey={labelCol} tick={{ fontSize: 10, fill: c.tick }} width={110} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: c.cursor }} />
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
        <XAxis dataKey={labelCol} tick={{ fontSize: 10, fill: c.tick }} interval={0} angle={-25} textAnchor="end" height={55} axisLine={{ stroke: c.axisLine }} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: c.tick }} axisLine={false} tickLine={false} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: c.cursor }} />
        <Bar dataKey={numericCol} radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {rows.map((_, i) => <Cell key={i} fill={colorAt(i)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ResultsView({ rows }) {
  const detected = rows?.length ? decideView(rows) : { type: "table" };
  const [view, setView] = useState("table"); // chart-vs-table toggle state - defaults to table regardless of the detected chart type
  const { labelCol, numericCol } = detected;

  if (!rows?.length) return <p className="empty">no rows returned</p>;

  const showToggle = detected.type !== "table";
  const total = numericCol ? rows.reduce((sum, r) => sum + (Number(r[numericCol]) || 0), 0) : null;

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
          <ChartHeader rows={rows} labelCol={labelCol} numericCol={numericCol} type={view} />
          <ChartView type={view} rows={rows} labelCol={labelCol} numericCol={numericCol} />
          <ChartLegend rows={rows} labelCol={labelCol} numericCol={numericCol} total={total} />
        </>
      )}
    </div>
  );
}

// Query lives in its own local accordion below the chart/table - it's a
// separate sibling in normal block flow, so opening/closing it only pushes
// content further down the page. It never touches card-main's box (width,
// height, or position), so the chart/table can't resize or shift.
function ResultCard({ msg }) {
  const [sqlOpen, setSqlOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(msg.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard unavailable, silently ignore */
    }
  }

  return (
    <div className={`card card-${msg.status}`}>
      <div className="card-head">
        <Verdict status={msg.status} />
        {msg.ms != null && <span className="ms">{msg.ms}ms</span>}
        {msg.sql && (
          <button
            type="button"
            className={`query-trigger${sqlOpen ? " active" : ""}`}
            onClick={() => setSqlOpen((o) => !o)}
            aria-expanded={sqlOpen}
          >
            query
          </button>
        )}
      </div>

      {msg.text && <p className="card-text">{msg.text}</p>}

      {msg.rows && (
        <div className="card-body">
          <div className="card-main">
            <ResultsView rows={msg.rows} />
          </div>
        </div>
      )}

      {msg.sql && (
        <div className={`sql-collapse${sqlOpen ? " open" : ""}`}>
          <div className="sql-collapse-inner">
            <div className="sql-panel-head">
              <span className="sql-panel-label">query</span>
              <button className={`sql-action${copied ? " copied" : ""}`} onClick={handleCopy}>
                {copied ? "copied" : "copy"}
              </button>
            </div>
            <pre className="sql">{msg.sql}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function SchemaModal({ open, onClose, data, loading, error, onRetry }) {
  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal schema-modal" role="dialog" aria-modal="true" aria-label="database schema" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h2 className="modal-title">database schema</h2>
            <p className="modal-sub">tables available to ask questions about</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="close schema">&times;</button>
        </div>

        <div className="modal-body">
          {loading && <p className="schema-status">loading schema&hellip;</p>}

          {error && (
            <div className="schema-status schema-error">
              <p>{error}</p>
              <button className="sql-action" onClick={onRetry}>retry</button>
            </div>
          )}

          {data && (
            <div className="schema-grid">
              {data.tables.map((t) => (
                <div className="schema-table" key={t.name}>
                  <div className="schema-table-head">
                    <span className="schema-table-name">{t.name}</span>
                    <span className="schema-table-count">{t.columns.length} cols</span>
                  </div>
                  <ul className="schema-columns">
                    {t.columns.map((c) => (
                      <li key={c.name} className="schema-column">
                        <span className="schema-col-name">{c.name}</span>
                        {c.pk && <span className="schema-badge schema-badge-pk">PK</span>}
                        {c.ref && <span className="schema-badge schema-badge-fk">&rarr; {c.ref}</span>}
                        {c.note && <span className="schema-col-note">{c.note}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [messages, setMessages] = useState(loadStoredMessages);
  const [loading, setLoading] = useState(false);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [schema, setSchema] = useState(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState(null);
  const [theme, setTheme] = useState(getInitialTheme);
  const transcriptRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  // persist the transcript on every change - savedAt is rewritten each time,
  // so the 24h expiry rolls forward as long as the chat stays active
  useEffect(() => {
    try {
      if (messages.length === 0) {
        localStorage.removeItem(HISTORY_KEY);
      } else {
        localStorage.setItem(HISTORY_KEY, JSON.stringify({ messages, savedAt: Date.now() }));
      }
    } catch {
      /* storage unavailable or full - the transcript just won't survive a reload */
    }
  }, [messages]);

  function clearHistory() {
    setMessages([]);
    setHistory([]);
    try {
      localStorage.removeItem(HISTORY_KEY);
    } catch {
      /* localStorage unavailable - nothing to clean up */
    }
  }

  // sync before paint so switching themes never flashes the previous palette
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* localStorage unavailable, theme just won't persist across reloads */
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

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

  async function loadSchema() {
    setSchemaLoading(true);
    setSchemaError(null);
    try {
      const res = await fetch(`${API_URL}/schema`);
      if (!res.ok) throw new Error(`request failed (${res.status})`);
      setSchema(await res.json());
    } catch (err) {
      setSchemaError(err.message || "failed to load schema");
    } finally {
      setSchemaLoading(false);
    }
  }

  function openSchema() {
    setSchemaOpen(true);
    if (!schema && !schemaLoading) loadSchema();
  }

  return (
    <ThemeContext.Provider value={theme}>
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <span className="dot" />
          <span className="brand">MultiBase</span>
          <span className="brand-sub">Query data in plain English → LLM converts it to SQL, resolves ambiguity, and visualizes results as tables, charts, or summaries.
</span>
        </div>
        <div className="topbar-right">
          <button
            type="button"
            role="switch"
            aria-checked={theme === "light"}
            className={`theme-toggle${theme === "light" ? " is-light" : ""}`}
            onClick={toggleTheme}
            title={`switch to ${theme === "dark" ? "light" : "dark"} mode`}
            aria-label="toggle color theme"
          >
            <span className="theme-toggle-knob">{theme === "light" ? <SunIcon /> : <MoonIcon />}</span>
          </button>
          <span className="topbar-sep">&middot;</span>
          <button
            type="button"
            className="schema-link"
            onClick={clearHistory}
            disabled={loading || messages.length === 0}
            title="clear saved chat history"
          >
            <TrashIcon /> clear
          </button>
          <span className="topbar-sep">&middot;</span>
          <button type="button" className="schema-link" onClick={openSchema}>
            <span className="schema-link-icon">&#9638;</span> schema
          </button>
          <span className="topbar-sep">&middot;</span>
          <span className="topbar-meta">postgres · claude</span>
        </div>
      </header>

      <main className="transcript" ref={transcriptRef}>
        {messages.length === 0 && <p className="empty-title">no submissions yet &mdash; try a prompt below</p>}

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

      <div className="composer">
        <div className="quick-prompts">
          <div className="quick-prompts-inner">
            <span className="quick-prompts-label">try</span>
            <div className="quick-prompts-row">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.text}
                  type="button"
                  className="quick-prompt-chip"
                  onClick={() => submitQuestion(s.text)}
                  disabled={loading}
                >
                  {s.text}
                </button>
              ))}
            </div>
          </div>
        </div>

        <form onSubmit={handleAsk} className="input-bar">
          <div className="input-bar-inner">
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
          </div>
        </form>
      </div>

      <SchemaModal
        open={schemaOpen}
        onClose={() => setSchemaOpen(false)}
        data={schema}
        loading={schemaLoading}
        error={schemaError}
        onRetry={loadSchema}
      />
    </div>
    </ThemeContext.Provider>
  );
}
