import { useState } from "react";
import { ChartBar, Table } from "@phosphor-icons/react";

// Card with a chart/table toggle — the table is the accessible fallback view.
export default function ChartCard({ title, sub, columns, tableRows, empty, children }) {
  const [showTable, setShowTable] = useState(false);
  const isEmpty = !tableRows?.length;

  return (
    <section className="chart-card" aria-label={title}>
      <div className="chart-head">
        <h2 className="chart-title">{title}</h2>
        {!isEmpty && (
          <button
            className="icon-btn"
            onClick={() => setShowTable((v) => !v)}
            aria-label={showTable ? `Show ${title} as chart` : `Show ${title} as table`}
            title={showTable ? "View as chart" : "View as table"}
          >
            {showTable ? <ChartBar size={17} /> : <Table size={17} />}
          </button>
        )}
      </div>
      <p className="chart-sub">{sub}</p>
      {isEmpty ? (
        <div className="chart-empty">{empty}</div>
      ) : showTable ? (
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((c) => <th key={c}>{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {tableRows.map((cells, i) => (
              <tr key={i}>
                {cells.map((cell, j) => (
                  <td key={j} className={j > 0 ? "num" : undefined}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        children
      )}
    </section>
  );
}
