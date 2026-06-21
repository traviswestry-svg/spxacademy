import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

function fmt(n) {
  if (n === undefined || n === null || Number.isNaN(Number(n))) return '—';
  return Number(n).toFixed(2);
}
function chartTime(iso) { return Math.floor(new Date(iso).getTime() / 1000); }
function clock(iso) { return iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'; }

function App() {
  const timerRef = useRef(null);

  const [bars, setBars] = useState([]);
  const [context, setContext] = useState(null);
  const [idx, setIdx] = useState(45);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [scenario, setScenario] = useState('news');
  const [trade, setTrade] = useState(null);
  const [score, setScore] = useState(null);
  const [coach, setCoach] = useState(null);
  const [tab, setTab] = useState('arena');
  const [lessons, setLessons] = useState([]);
  const [scenarios, setScenarios] = useState({});
  const [journal, setJournal] = useState(() => JSON.parse(localStorage.getItem('spxAcademyJournal') || '[]'));

  const current = bars[idx];
  const visible = useMemo(() => bars.slice(0, idx + 1), [bars, idx]);
  const stats = useMemo(() => {
    if (!journal.length) return { reps: 0, avg: 0, win: 0, chase: 0 };
    const reps = journal.length;
    const avg = journal.reduce((s, j) => s + Number(j.score || 0), 0) / reps;
    const wins = journal.filter(j => Number(j.pnl) > 0).length;
    const chase = journal.filter(j => (j.mistakes || []).includes('chased extension')).length;
    return { reps, avg, win: (wins / reps) * 100, chase: (chase / reps) * 100 };
  }, [journal]);

  async function loadLessons() {
    try {
      const res = await fetch(`${API_BASE}/api/trainer/lessons`);
      const data = await res.json();
      setLessons(data.lessons || []);
      setScenarios(data.scenarios || {});
    } catch (e) {}
  }

  async function loadSession(nextScenario = scenario) {
    setLoading(true); setPlaying(false); setTrade(null); setScore(null); setCoach(null); setIdx(45);
    const res = await fetch(`${API_BASE}/api/trainer/session?scenario=${nextScenario}`);
    const data = await res.json();
    setBars(data.bars || []);
    setContext(data.context || null);
    setLoading(false);
  }

  useEffect(() => { loadLessons(); loadSession('news'); }, []);

  useEffect(() => {
    if (!playing) return;
    timerRef.current = setInterval(() => stepForward(), 850);
    return () => clearInterval(timerRef.current);
  }, [playing, idx, trade, bars]);

  function stepForward() {
    setIdx(prev => {
      const next = Math.min(prev + 1, Math.max(bars.length - 1, 0));
      if (trade && !trade.exitIndex && next - trade.entryIndex >= 15) setPlaying(false);
      return next;
    });
  }
  function changeScenario(e) {
    const next = e.target.value;
    setScenario(next);
    loadSession(next);
  }
  function enter(direction) {
    if (!current || trade?.entryIndex) return;
    setScore(null);
    setTrade({ direction, entryIndex: idx, entryPrice: current.close, entryTime: current.time });
  }
  async function exitTrade() {
    if (!trade || trade.exitIndex || !current || idx === trade.entryIndex) return;
    const completed = { ...trade, exitIndex: idx, exitPrice: current.close, exitTime: current.time };
    setTrade(completed);
    const res = await fetch(`${API_BASE}/api/trainer/score`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...completed, bars }) });
    const data = await res.json();
    setScore(data); setPlaying(false); setTab('critique');
    const row = { at: new Date().toLocaleString(), scenario: context?.scenarioLabel, direction: completed.direction, entry: completed.entryPrice, exit: completed.exitPrice, score: data.score, grade: data.grade, pnl: data.pnlPoints, mistakes: data.mistakes || [] };
    const nextJournal = [row, ...journal].slice(0, 50);
    setJournal(nextJournal); localStorage.setItem('spxAcademyJournal', JSON.stringify(nextJournal));
  }
  async function askCoach(nextIdx = idx) {
    const res = await fetch(`${API_BASE}/api/trainer/coach`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bars, index: nextIdx }) });
    setCoach(await res.json());
  }
  function resetJournal() { localStorage.removeItem('spxAcademyJournal'); setJournal([]); }

  const tradeAge = trade && !trade.exitIndex ? idx - trade.entryIndex : trade?.exitIndex ? trade.exitIndex - trade.entryIndex : 0;
  const unreal = trade && !trade.exitIndex && current ? (current.close - trade.entryPrice) * (trade.direction === 'long' ? 1 : -1) : null;

  return <div className="app">
    <header>
      <div>
        <h1>SPX 0DTE Academy Dashboard v1.0</h1>
        <p>Training-only replay simulator for reading candles, practicing 15-minute SPX-style trades, and receiving entry/exit critique.</p>
      </div>
      <div className="headerActions">
        <select value={scenario} onChange={changeScenario}>{Object.entries(scenarios).map(([key, val]) => <option key={key} value={key}>{val.label}</option>)}</select>
        <button onClick={() => loadSession(scenario)}>New Session</button>
      </div>
    </header>

    {loading ? <div className="panel">Loading Academy simulator…</div> : <>
      <section className="topGrid">
        <div className="card"><span>Scenario</span><strong>{context?.scenarioLabel}</strong><em>{context?.difficulty}</em></div>
        <div className="card"><span>Replay Time</span><strong>{clock(current?.time)}</strong><em>Candle {idx + 1} / {bars.length}</em></div>
        <div className="card"><span>Trade Clock</span><strong className={tradeAge >= 12 ? 'danger' : ''}>{trade ? `${tradeAge}/15 min` : 'No trade'}</strong><em>Exit before minute 15</em></div>
        <div className="card"><span>Report Card</span><strong>{stats.reps} reps</strong><em>Avg {stats.avg.toFixed(0)} · Win {stats.win.toFixed(0)}% · Chase {stats.chase.toFixed(0)}%</em></div>
      </section>

      <nav className="tabs">
        {['arena','coach','critique','journal','curriculum'].map(t => <button key={t} onClick={() => setTab(t)} className={tab === t ? 'active' : ''}>{t === 'arena' ? 'Training Arena' : t === 'coach' ? 'Candle Coach' : t === 'critique' ? 'Trade Critique' : t === 'journal' ? 'Performance Journal' : 'Academy Lessons'}</button>)}
      </nav>

      <main className="layout">
        <section className="chartPanel">
          <div className="chartToolbar">
            <button onClick={() => setIdx(Math.max(20, idx - 1))}>Back</button>
            <button onClick={stepForward}>Next Candle</button>
            <button onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</button>
            <button className="long" disabled={!!trade?.entryIndex} onClick={() => enter('long')}>Enter CALL Bias</button>
            <button className="short" disabled={!!trade?.entryIndex} onClick={() => enter('short')}>Enter PUT Bias</button>
            <button className="exit" disabled={!trade || !!trade.exitIndex || idx === trade.entryIndex} onClick={exitTrade}>Exit / Score</button>
            <button onClick={() => askCoach()}>Coach This Candle</button>
          </div>
          <SvgChart bars={visible} trade={trade} idx={idx} />
          <div className="legend"><span className="ema8">EMA8</span><span className="ema21">EMA21</span><span className="vwap">VWAP</span><span>Training only — no orders are placed.</span></div>
        </section>

        <aside className="side">
          {tab === 'arena' && <Arena current={current} trade={trade} unreal={unreal} context={context} />}
          {tab === 'coach' && <Coach current={current} coach={coach} askCoach={askCoach} />}
          {tab === 'critique' && <Critique score={score} />}
          {tab === 'journal' && <Journal journal={journal} resetJournal={resetJournal} />}
          {tab === 'curriculum' && <Curriculum lessons={lessons} />}
        </aside>
      </main>
    </>}
  </div>;
}

function SvgChart({ bars, trade, idx }) {
  if (!bars || bars.length < 2) {
    return <div className="chart fallbackChart"><p>Waiting for chart data…</p></div>;
  }

  const width = 1120;
  const height = 480;
  const pad = { top: 20, right: 62, bottom: 36, left: 14 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const prices = [];
  bars.forEach(b => {
    prices.push(b.high, b.low, b.ema8, b.ema21, b.vwap);
  });
  let min = Math.min(...prices);
  let max = Math.max(...prices);
  const range = Math.max(max - min, 1);
  min -= range * 0.08;
  max += range * 0.08;
  const y = price => pad.top + ((max - price) / (max - min)) * plotH;
  const x = i => pad.left + (i / Math.max(bars.length - 1, 1)) * plotW;
  const candleW = Math.max(3, Math.min(10, plotW / bars.length * 0.55));
  const linePath = key => bars.map((b, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(b[key]).toFixed(1)}`).join(' ');
  const grid = Array.from({ length: 5 }, (_, i) => min + ((max - min) * i / 4));

  const entryIndex = trade?.entryIndex;
  const exitIndex = trade?.exitIndex;

  return <div className="chart svgChartWrap">
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="SPX 0DTE training candlestick chart">
      <rect x="0" y="0" width={width} height={height} fill="#080b12" />
      {grid.map((g, i) => <g key={i}>
        <line x1={pad.left} x2={width - pad.right} y1={y(g)} y2={y(g)} stroke="#172033" strokeWidth="1" />
        <text x={width - pad.right + 8} y={y(g) + 4} fill="#94a3b8" fontSize="12">{g.toFixed(1)}</text>
      </g>)}
      <path d={linePath('ema8')} fill="none" stroke="#60a5fa" strokeWidth="2" opacity="0.9" />
      <path d={linePath('ema21')} fill="none" stroke="#a78bfa" strokeWidth="2" opacity="0.85" />
      <path d={linePath('vwap')} fill="none" stroke="#f59e0b" strokeWidth="2.5" opacity="0.95" />
      {bars.map((b, i) => {
        const up = b.close >= b.open;
        const color = up ? '#22c55e' : '#ef4444';
        const bodyTop = Math.min(y(b.open), y(b.close));
        const bodyH = Math.max(Math.abs(y(b.open) - y(b.close)), 2);
        return <g key={i}>
          <line x1={x(i)} x2={x(i)} y1={y(b.high)} y2={y(b.low)} stroke={color} strokeWidth="1.4" />
          <rect x={x(i) - candleW / 2} y={bodyTop} width={candleW} height={bodyH} fill={color} rx="1" />
        </g>;
      })}
      {entryIndex !== undefined && entryIndex <= idx && bars[entryIndex] && <g>
        <line x1={x(entryIndex)} x2={x(entryIndex)} y1={pad.top} y2={height - pad.bottom} stroke="#22c55e" strokeDasharray="5 5" strokeWidth="2" />
        <text x={x(entryIndex) + 6} y={pad.top + 18} fill="#22c55e" fontSize="13" fontWeight="800">ENTRY</text>
      </g>}
      {exitIndex !== undefined && exitIndex <= idx && bars[exitIndex] && <g>
        <line x1={x(exitIndex)} x2={x(exitIndex)} y1={pad.top} y2={height - pad.bottom} stroke="#f97316" strokeDasharray="5 5" strokeWidth="2" />
        <text x={x(exitIndex) + 6} y={pad.top + 36} fill="#f97316" fontSize="13" fontWeight="800">EXIT</text>
      </g>}
      <text x={pad.left} y={height - 12} fill="#94a3b8" fontSize="12">Synthetic SPX replay candles · chart rendered locally with SVG</text>
    </svg>
  </div>;
}

function Arena({ current, trade, unreal, context }) {
  return <>
    <div className="panel"><h2>Current Candle Read</h2><p><b>Close:</b> {fmt(current?.close)} | <b>VWAP:</b> {fmt(current?.vwap)}</p><p><b>EMA8/21/50:</b> {fmt(current?.ema8)} / {fmt(current?.ema21)} / {fmt(current?.ema50)}</p><p><b>Candle:</b> {current?.candle?.shape} · {current?.candle?.direction}</p><p className="hint">Body {current?.candle?.bodyPct}% · Upper wick {current?.candle?.upperWickPct}% · Lower wick {current?.candle?.lowerWickPct}%</p></div>
    <div className="panel"><h2>Open Trade</h2>{trade ? <><p><b>{trade.direction.toUpperCase()}</b> from {fmt(trade.entryPrice)}</p><p><b>Unrealized:</b> <span className={unreal >= 0 ? 'good' : 'bad'}>{unreal === null ? '—' : `${unreal >= 0 ? '+' : ''}${fmt(unreal)} pts`}</span></p><p className="hint">Academy rule: manage the trade inside 15 minutes. Do not hold and hope.</p></> : <p>No trade yet. Read trend, wait for value, then require confirmation.</p>}</div>
    <div className="panel checklist"><h2>Before Entry Checklist</h2><label><input type="checkbox"/> VWAP agrees with direction</label><label><input type="checkbox"/> EMA8/EMA21 aligned</label><label><input type="checkbox"/> Not chasing far from value</label><label><input type="checkbox"/> Candle confirms direction</label><label><input type="checkbox"/> Exit plan under 15 minutes</label></div>
    <div className="panel warning"><h2>Scenario Brief</h2><p>{context?.warning}</p></div>
  </>;
}
function Coach({ current, coach, askCoach }) {
  return <><div className="panel coach"><h2>Why This Candle Matters</h2><p>{current?.candle?.lesson}</p><button onClick={() => askCoach()}>Generate Coach Verdict</button></div>{coach && <div className="panel"><h2>Coach Verdict</h2><p>{coach.lesson}</p><div className="scoreGrid"><span>Long {coach.longQuality?.score}/100</span><span>Short {coach.shortQuality?.score}/100</span><span>Bias {coach.bias}</span><span>{coach.bestAction}</span></div></div>}<div className="panel"><h2>Wait vs Trade Rule</h2><p>If both long and short quality are under 78, the correct Academy answer is usually WAIT. 0DTE survival comes from passing on mediocre candles.</p></div></>;
}
function Critique({ score }) {
  if (!score) return <div className="panel"><h2>Trade Critique</h2><p>Complete a trade to receive your grade, entry critique, exit critique, MFE/MAE, and mistake tags.</p></div>;
  return <div className="panel score"><h2>Trade Score: {score.score}/100 · {score.grade}</h2><p>{score.summary}</p><div className="scoreGrid"><span>Entry {score.entryScore}/60</span><span>Exit {score.exitScore}/40</span><span>P/L {score.pnlPoints > 0 ? '+' : ''}{score.pnlPoints} pts</span><span>MFE Capture {score.capturePct}%</span></div>{score.mistakes?.length > 0 && <p className="bad"><b>Mistake tags:</b> {score.mistakes.join(', ')}</p>}<ul>{score.details?.map((d, i) => <li key={i}>{d}</li>)}</ul></div>;
}
function Journal({ journal, resetJournal }) {
  return <div className="panel journal"><h2>Performance Journal</h2>{journal.length === 0 ? <p>No scored reps yet.</p> : <table><thead><tr><th>Time</th><th>Scenario</th><th>Side</th><th>Entry</th><th>Exit</th><th>P/L</th><th>Score</th></tr></thead><tbody>{journal.map((j, i) => <tr key={i}><td>{j.at}</td><td>{j.scenario}</td><td>{j.direction}</td><td>{fmt(j.entry)}</td><td>{fmt(j.exit)}</td><td className={j.pnl > 0 ? 'good' : 'bad'}>{j.pnl > 0 ? '+' : ''}{fmt(j.pnl)}</td><td>{j.score} / {j.grade}</td></tr>)}</tbody></table>}<button onClick={resetJournal}>Clear Journal</button></div>;
}
function Curriculum({ lessons }) {
  return <div className="curriculum">{lessons.map((l, i) => <div className="panel" key={i}><h2>{l.title}</h2><p>{l.body}</p><ul>{l.checks?.map((c, n) => <li key={n}>{c}</li>)}</ul></div>)}<div className="panel"><h2>How to Use This Dashboard</h2><ol><li>Pick a scenario.</li><li>Press Play or Next Candle.</li><li>Say out loud: trend, value, candle, risk.</li><li>Enter CALL/PUT bias only when the setup is clean.</li><li>Exit within 15 minutes and review the critique.</li></ol></div></div>;
}

createRoot(document.getElementById('root')).render(<App />);
