import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, getAgents, getLogs, getState, resetDemo, setScenario, stepCycle } from "./api.js";
import Controls from "./components/Controls.jsx";
import KpiCards from "./components/KpiCards.jsx";
import ServerCard from "./components/ServerCard.jsx";
import AgentPanels from "./components/AgentPanels.jsx";
import UtilChart from "./components/UtilChart.jsx";
import BeforeAfter from "./components/BeforeAfter.jsx";
import ActivityLog from "./components/ActivityLog.jsx";

const AUTO_INTERVAL_MS = 2500; // simulation runs one cycle every 2.5 seconds

export default function App() {
  const [state, setState] = useState(null);
  const [agents, setAgents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [auto, setAuto] = useState(false);
  const busyRef = useRef(false); // stops two requests from overlapping

  // Fetch everything the dashboard shows.
  const refresh = useCallback(async () => {
    const [s, a, l] = await Promise.all([getState(), getAgents(), getLogs()]);
    setState(s);
    setAgents(a.agents);
    setLogs(l.logs);
  }, []);

  // Run a backend action, then refresh the screen.
  const act = useCallback(
    async (fn) => {
      if (busyRef.current) return;
      busyRef.current = true;
      try {
        await fn();
        await refresh();
        setError("");
      } catch (e) {
        setAuto(false);
        setError(
          `Cannot reach the backend at ${API_URL}. Start it with: uvicorn app.main:app --host 127.0.0.1 --port 8000 (${e.message})`
        );
      } finally {
        busyRef.current = false;
      }
    },
    [refresh]
  );

  // Load initial data once.
  useEffect(() => {
    act(async () => {});
  }, [act]);

  // Simulation: one cycle every few seconds while "auto" is on.
  useEffect(() => {
    if (!auto) return undefined;
    const id = setInterval(() => act(stepCycle), AUTO_INTERVAL_MS);
    return () => clearInterval(id);
  }, [auto, act]);

  const onScenario = (name) => {
    setAuto(false);
    act(() => setScenario(name));
  };
  const onReset = () => {
    setAuto(false);
    act(resetDemo);
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Cloud Resource Allocation</h1>
          <p className="subtitle">Multi-Agent Resource Management System</p>
        </div>
        <span className="env-label">Simulated Environment</span>
      </header>

      {error && <div className="error-box">{error}</div>}

      {!state ? (
        <p className="muted">Connecting to the simulation backend...</p>
      ) : (
        <>
          <section className="section">
            <h2>Controls</h2>
            <Controls
              scenario={state.scenario}
              cycle={state.cycle}
              auto={auto}
              onScenario={onScenario}
              onStep={() => act(stepCycle)}
              onStart={() => setAuto(true)}
              onStop={() => setAuto(false)}
              onReset={onReset}
            />
          </section>

          <section className="section">
            <h2>Overview</h2>
            <KpiCards kpis={state.kpis} costNote={state.cost_note} />
          </section>

          <section className="section">
            <h2>Server Monitoring</h2>
            {state.pending_jobs.length > 0 && (
              <p className="note">
                Waiting for placement: {state.pending_jobs.map((j) => `${j.name} (${j.cpu} vCPU, ${j.mem} GB)`).join(", ")}
              </p>
            )}
            <div className="server-grid">
              {state.servers.map((s) => (
                <ServerCard key={s.id} server={s} />
              ))}
            </div>
          </section>

          <section className="section">
            <h2>Agent Activity</h2>
            <AgentPanels agents={agents} />
          </section>

          <section className="section">
            <h2>Before and After</h2>
            <BeforeAfter change={state.last_change} lastCycle={state.last_cycle} />
          </section>

          <section className="section">
            <h2>Decision Log</h2>
            <ActivityLog logs={logs} />
          </section>

          <section className="section">
            <h2>Performance Chart</h2>
            <UtilChart history={state.history} servers={state.servers} highCpu={state.thresholds.high_cpu} />
          </section>
        </>
      )}

      <footer className="footer">
        Simulated, rule-based prototype. No real cloud resources are used and costs are made-up hourly rates.
      </footer>
    </div>
  );
}
