function Row({ label, before, after, delta, unit }) {
  const sign = delta > 0 ? "+" : "";
  return (
    <tr>
      <th scope="row">{label}</th>
      <td className="num">{before}{unit}</td>
      <td className="num">{after}{unit}</td>
      <td className="num">{delta === 0 ? "no change" : `${sign}${Number(delta.toFixed(2))}${unit}`}</td>
    </tr>
  );
}

function describe(a) {
  if (a.type === "place") return `Placed ${a.job} on ${a.to}`;
  if (a.type === "migrate") return `Moved ${a.job} from ${a.from} to ${a.to}`;
  if (a.type === "power_on") return `Powered on ${a.server}`;
  if (a.type === "power_off") return `Moved all jobs off ${a.server} and powered it off`;
  return a.type;
}

export default function BeforeAfter({ change, lastCycle }) {
  if (!change) {
    return (
      <div className="card">
        <p className="muted">
          Nothing has changed yet. Press Run One Cycle. When an agent moves a workload or switches a server on or
          off, the comparison appears here.
        </p>
      </div>
    );
  }
  return (
    <div className="card">
      <p className="note">
        Latest change: cycle {change.cycle}
        {lastCycle && lastCycle.cycle !== change.cycle ? ` (cycle ${lastCycle.cycle} made no change)` : ""}.
        Averages cover powered-on servers only, so switching a server on or off also moves them.
      </p>
      <ul className="change-list">
        {change.changes.map((c, i) => (
          <li key={i}>{describe(c)}</li>
        ))}
      </ul>
      <div className="table-scroll">
        <table className="compare-table">
          <thead>
            <tr>
              <th></th>
              <th>Before</th>
              <th>After</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            <Row label="Highest server CPU" before={change.before.max_cpu} after={change.after.max_cpu} delta={change.delta.max_cpu} unit="%" />
            <Row label="Average CPU" before={change.before.avg_cpu} after={change.after.avg_cpu} delta={change.delta.avg_cpu} unit="%" />
            <Row label="Average memory" before={change.before.avg_mem} after={change.after.avg_mem} delta={change.delta.avg_mem} unit="%" />
            <Row label="Active servers" before={change.before.active_servers} after={change.after.active_servers} delta={change.delta.active_servers} unit="" />
            <Row label="Hourly cost ($)" before={change.before.hourly_cost.toFixed(2)} after={change.after.hourly_cost.toFixed(2)} delta={change.delta.hourly_cost} unit="" />
          </tbody>
        </table>
      </div>
      <details>
        <summary>Per-server detail</summary>
        <ul className="detail-list">
          {change.before.servers.map((b, i) => {
            const a = change.after.servers[i];
            return (
              <li key={b.id}>
                {b.name}: CPU {b.powered_on ? `${b.cpu_pct}%` : "off"} to {a.powered_on ? `${a.cpu_pct}%` : "off"},
                workloads {b.jobs} to {a.jobs}
              </li>
            );
          })}
        </ul>
      </details>
    </div>
  );
}
