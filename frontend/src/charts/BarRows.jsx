// Horizontal bar rows: direct labels + value, hover/focus tooltip (keyboard reachable).
export default function BarRows({ rows }) {
  return (
    <div>
      {rows.map((row) => (
        <div className="bar-row" key={row.label} tabIndex={0}>
          <span className="bar-label">{row.label}</span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                width: `${Math.max(0, Math.min(1, row.frac)) * 100}%`,
                background: row.color,
              }}
            />
          </div>
          <span className="bar-value num">
            {row.value}
            {row.note && <span className="bar-note"> {row.note}</span>}
          </span>
          {row.tip && <div className="bar-tip" role="tooltip">{row.tip}</div>}
        </div>
      ))}
    </div>
  );
}
