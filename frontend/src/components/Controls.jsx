const SCENARIOS = [
  { key: "normal", label: "Normal Load" },
  { key: "spike", label: "Traffic Spike" },
  { key: "underused", label: "Underutilization" },
];

export default function Controls({ scenario, cycle, auto, onScenario, onStep, onStart, onStop, onReset }) {
  return (
    <div className="controls">
      <div className="button-row">
        <div className="button-group" role="group" aria-label="Scenarios">
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              className={"btn" + (scenario.key === s.key ? " selected" : "")}
              onClick={() => onScenario(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="button-group" role="group" aria-label="Simulation">
          <button className="btn primary" onClick={onStep} disabled={auto}>
            Run One Cycle
          </button>
          <button className="btn" onClick={onStart} disabled={auto}>
            Start Simulation
          </button>
          <button className="btn" onClick={onStop} disabled={!auto}>
            Stop
          </button>
          <button className="btn" onClick={onReset}>
            Reset
          </button>
        </div>
      </div>
      <p className="note">
        Scenario: <strong>{scenario.title}</strong>. Cycle {cycle}
        {auto ? " (running)" : ""}. {scenario.description}
      </p>
    </div>
  );
}
