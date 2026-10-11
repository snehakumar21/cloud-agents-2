const STATUS_TEXT = {
  healthy: "Healthy",
  high: "High load",
  overloaded: "Overloaded",
  underutilized: "Underutilized",
  off: "Powered off",
};

// One plain progress bar.
function Meter({ label, pct }) {
  return (
    <div className="meter">
      <div className="meter-row">
        <span>{label}</span>
        <span className="num">{pct.toFixed(1)}%</span>
      </div>
      <div
        className="track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
      >
        <div className="fill" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
    </div>
  );
}

export default function ServerCard({ server }) {
  const s = server;
  const strong = s.status === "high" || s.status === "overloaded";
  return (
    <article className="card server">
      <header className="server-head">
        <h3>{s.name}</h3>
        <span className={"status" + (strong ? " strong" : "")}>{STATUS_TEXT[s.status] || s.status}</span>
      </header>

      {!s.powered_on ? (
        <p className="muted">Powered off. It adds no capacity and no cost until it is switched on.</p>
      ) : (
        <>
          <Meter label="CPU" pct={s.cpu_pct} />
          <Meter label="Memory" pct={s.mem_pct} />
          <p className="workloads">
            <span className="muted">Workloads: </span>
            {s.jobs.length === 0 ? "none" : s.jobs.map((j) => j.name).join(", ")}
          </p>
        </>
      )}

      <details>
        <summary>Details</summary>
        <ul className="detail-list">
          <li>
            Capacity: {s.cpu_capacity} vCPU, {s.mem_capacity} GB RAM
          </li>
          {s.powered_on && (
            <li>
              In use: {s.cpu_used.toFixed(1)} vCPU, {s.mem_used.toFixed(1)} GB
            </li>
          )}
          <li>Cost: ${s.hourly_cost.toFixed(2)} per hour (simulated)</li>
          {s.jobs.map((j) => (
            <li key={j.name}>
              {j.name}: {j.cpu} vCPU, {j.mem} GB
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}
