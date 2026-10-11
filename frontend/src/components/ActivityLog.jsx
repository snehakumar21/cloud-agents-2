export default function ActivityLog({ logs }) {
  const newestFirst = [...logs].reverse();
  return (
    <div className="log-wrap">
      <table className="log-table">
        <thead>
          <tr>
            <th className="col-cycle">Cycle</th>
            <th className="col-agent">Agent</th>
            <th>Action</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {newestFirst.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No decisions yet.
              </td>
            </tr>
          )}
          {newestFirst.map((l) => (
            <tr key={l.id}>
              <td className="num">{l.cycle}</td>
              <td>{l.agent}</td>
              <td>
                <span className="log-action">{l.decision}</span>
                <span className="log-why">{l.explanation}</span>
              </td>
              <td>{l.result}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
