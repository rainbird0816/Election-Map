import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

// 정당별 의석 도넛 다이어그램. rows=[{label,color,value}]
export default function SeatChart({ rows, unit = "석", height = 170 }) {
  const data = (rows || []).filter((r) => r.value > 0);
  if (!data.length) return null;
  const total = data.reduce((s, r) => s + r.value, 0);
  return (
    <div className="seatchart">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data} dataKey="value" nameKey="label"
            cx="50%" cy="50%" innerRadius={45} outerRadius={70}
            startAngle={90} endAngle={-270} paddingAngle={1}
          >
            {data.map((r, i) => <Cell key={i} fill={r.color || "#bbb"} />)}
          </Pie>
          <Tooltip formatter={(v, n) => [`${v}${unit} (${Math.round((v / total) * 100)}%)`, n]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="seatchart-center">총 {total}{unit}</div>
    </div>
  );
}
