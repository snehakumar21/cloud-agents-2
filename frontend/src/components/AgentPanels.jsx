export default function AgentPanels({ agents }) {
  return (
    <div className="agent-grid">
      {agents.map((a) => (
        <article className="card agent" key={a.key}>
          <h3>{a.name}</h3>
          <p className="agent-text">
            {a.cycle === 0 ? "Waiting for the first cycle. Press Run One Cycle." : a.action}
          </p>
          {a.cycle !== 0 && (
            <details>
              <summary>Details</summary>
              <p className="detail-text">
                <strong>Role:</strong> {a.role}
              </p>
              <p className="detail-text">
                <strong>Observed:</strong> {a.observation}
              </p>
              {a.data && <pre>{JSON.stringify(a.data, null, 2)}</pre>}
            </details>
          )}
        </article>
      ))}
    </div>
  );
}
