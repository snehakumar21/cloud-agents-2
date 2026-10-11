import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Muted colours plus different line styles, so the lines are easy to tell apart.
const STYLES = [
  { stroke: "#3B6EA8", dash: undefined },
  { stroke: "#374151", dash: "6 4" },
  { stroke: "#9CA3AF", dash: "2 3" },
];

export default function UtilChart({ history, servers, highCpu }) {
  return (
    <div className="card chart-card">
      <p className="note">
        CPU usage per server. Samples -5 to 0 are seeded starting data; each cycle adds one new sample. A gap means
        the server was powered off.
      </p>
      <div className="chart-box">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="3 3" />
            <XAxis dataKey="label" stroke="#6B7280" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} stroke="#6B7280" tick={{ fontSize: 12 }} unit="%" />
            <Tooltip
              contentStyle={{ background: "#FFFFFF", border: "1px solid #E5E7EB", borderRadius: 6, color: "#1F2937" }}
              formatter={(v) => (v === null || v === undefined ? "off" : `${Number(v).toFixed(1)}%`)}
              labelFormatter={(l) => `Sample ${l}`}
            />
            <Legend />
            <ReferenceLine
              y={highCpu}
              stroke="#6B7280"
              strokeDasharray="5 4"
              label={{ value: `high load ${highCpu}%`, fill: "#6B7280", fontSize: 11, position: "insideTopRight" }}
            />
            {servers.map((s, i) => (
              <Line
                key={s.id}
                type="monotone"
                dataKey={s.id}
                name={s.name}
                stroke={STYLES[i % STYLES.length].stroke}
                strokeDasharray={STYLES[i % STYLES.length].dash}
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
