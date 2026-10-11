import { useCallback, useEffect, useState } from "react";
import { getAwsInventory } from "../api.js";

export default function AwsInventory() {
  const [inventory, setInventory] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setInventory(await getAwsInventory());
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <section className="section">
      <h2>AWS EC2 Read-Only Inventory</h2>
      <p className="note">Discovery and CloudWatch metrics only. This project does not make AWS changes.</p>
      <button className="btn" onClick={refresh} disabled={loading}>{loading ? "Loading AWS…" : "Refresh AWS inventory"}</button>
      {error && <div className="error-box">AWS inventory unavailable: {error}. Check backend credentials, region, IAM permissions, and boto3 installation.</div>}
      {inventory && <>
        <p className="note">Region: <strong>{inventory.region}</strong>. {inventory.count} instances. {inventory.metric_note}</p>
        {inventory.managed_tag_filter && <p className="note">Tag filter: {inventory.managed_tag_filter.key}={inventory.managed_tag_filter.value}</p>}
        {inventory.instances.length === 0 ? <p className="muted">No EC2 instances matched the configured filter.</p> :
          <div className="server-grid">
            {inventory.instances.map((instance) => (
              <article className="card server" key={instance.id}>
                <header className="server-head">
                  <h3>{instance.name}</h3>
                  <span className={"status" + (["high", "overloaded"].includes(instance.status) ? " strong" : "")}>{instance.state}{instance.status === "unknown" ? " · CPU unavailable" : ""}</span>
                </header>
                <p><strong>{instance.instance_type}</strong> · {instance.id}</p>
                <p>CPU (1h avg): {instance.cpu_pct == null ? "Unavailable" : `${instance.cpu_pct}%`}</p>
                <p>Memory: {instance.memory_gib == null ? "Instance memory metadata unavailable" : `${instance.memory_gib} GiB capacity; utilization unavailable`}</p>
                <p>Availability Zone: {instance.availability_zone || "—"}</p>
                <p>Private IP: {instance.private_ip || "—"}</p>
                <p className="note">Actions disabled · recommendations require a separate approval workflow.</p>
              </article>
            ))}
          </div>}
      </>}
    </section>
  );
}
