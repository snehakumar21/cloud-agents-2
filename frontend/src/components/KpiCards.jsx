export default function KpiCards({ kpis, costNote }) {
  const cards = [
    { label: "Active Servers", value: `${kpis.active_servers} of ${kpis.total_servers}` },
    { label: "Average CPU Usage", value: `${kpis.avg_cpu.toFixed(1)}%` },
    { label: "Average Memory Usage", value: `${kpis.avg_mem.toFixed(1)}%` },
    { label: "Estimated Hourly Cost", value: `$${kpis.hourly_cost.toFixed(2)}`, title: costNote },
  ];
  return (
    <div className="metric-grid">
      {cards.map((c) => (
        <div className="card metric" key={c.label} title={c.title}>
          <span className="metric-label">{c.label}</span>
          <span className="metric-value">{c.value}</span>
        </div>
      ))}
    </div>
  );
}
