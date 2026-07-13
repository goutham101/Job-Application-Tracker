import { useCallback, useEffect, useState } from "react";
import { ArrowClockwise, WarningCircle } from "@phosphor-icons/react";
import { api } from "../api.js";
import { SOURCE_LABELS, STAGE_LABELS, STAGE_SHORT, stageColor } from "../constants.js";
import { fmtDays, fmtPct } from "../format.js";
import BarRows from "../charts/BarRows.jsx";
import ChartCard from "../charts/ChartCard.jsx";

const RAMP = ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)", "var(--ramp-4)", "var(--ramp-5)", "var(--ramp-6)"];

export default function AnalyticsView() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [funnel, timeInStage, bySource, byStage] = await Promise.all([
        api.funnel(),
        api.timeInStage(),
        api.bySource(),
        api.byStage(),
      ]);
      setData({ funnel, timeInStage, bySource, byStage });
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <main className="page">
        <div className="error-banner" role="alert">
          <WarningCircle size={18} aria-hidden />
          Couldn’t load analytics: {error}
          <button className="btn btn-ghost" onClick={load}>
            <ArrowClockwise size={15} aria-hidden /> Retry
          </button>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="page">
        <div className="charts">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: 240 }} />
          ))}
        </div>
      </main>
    );
  }

  const { funnel, timeInStage, bySource, byStage } = data;

  // ── Funnel ────────────────────────────────────────────────────
  const maxReached = Math.max(...funnel.map((s) => s.reached), 1);
  const anyReached = funnel.some((s) => s.reached > 0);
  const funnelRows = funnel.map((s, i) => ({
    label: STAGE_LABELS[s.stage],
    frac: s.reached / maxReached,
    color: RAMP[i],
    value: String(s.reached),
    note: s.conversion_to_next != null ? `· ${fmtPct(s.conversion_to_next)} →` : "",
    tip:
      `${s.reached} reached · ${s.still_pending} still here` +
      (s.conversion_to_next != null
        ? ` · ${fmtPct(s.conversion_to_next)} advance`
        : ""),
  }));
  let biggestDrop = null;
  for (let i = 0; i < funnel.length - 1; i++) {
    const c = funnel[i].conversion_to_next;
    if (c != null && (biggestDrop == null || c < biggestDrop.c)) {
      biggestDrop = { c, from: STAGE_LABELS[funnel[i].stage], to: STAGE_LABELS[funnel[i + 1].stage] };
    }
  }

  // ── Time in stage ─────────────────────────────────────────────
  const slowestFirst = [...timeInStage].sort((a, b) => b.avg_days - a.avg_days);
  const maxDays = Math.max(...timeInStage.map((t) => t.avg_days), 0.1);
  const timeRows = slowestFirst.map((t) => ({
    label: `${STAGE_SHORT[t.from_stage]} → ${STAGE_SHORT[t.to_stage]}`,
    frac: t.avg_days / maxDays,
    color: "var(--bar)",
    value: fmtDays(t.avg_days),
    tip: `${STAGE_LABELS[t.from_stage]} → ${STAGE_LABELS[t.to_stage]}: ${t.transitions} transition${t.transitions === 1 ? "" : "s"}, averaging ${fmtDays(t.avg_days)}`,
  }));

  // ── Response rate by source ───────────────────────────────────
  const sourceRows = bySource.map((s) => ({
    label: SOURCE_LABELS[s.source],
    frac: s.response_rate,
    color: "var(--bar)",
    value: fmtPct(s.response_rate),
    note: `(${s.responded}/${s.total})`,
    tip: `${s.responded} of ${s.total} applications got a response`,
  }));

  // ── Current stage mix ─────────────────────────────────────────
  const maxCount = Math.max(...byStage.map((s) => s.count), 1);
  const mixRows = byStage.map((s) => ({
    label: STAGE_LABELS[s.stage],
    frac: s.count / maxCount,
    color: stageColor(s.stage),
    value: String(s.count),
    tip: `${s.count} application${s.count === 1 ? "" : "s"} currently at ${STAGE_LABELS[s.stage]}`,
  }));

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-sub">Computed in SQL from the append-only event log.</p>
        </div>
      </div>
      <div className="charts">
        <ChartCard
          title="Pipeline funnel"
          sub={
            anyReached && biggestDrop
              ? `Biggest drop-off: ${biggestDrop.from} → ${biggestDrop.to} (${fmtPct(biggestDrop.c)} advance). Skipped stages count as passed through.`
              : "How far applications get. Skipped stages count as passed through."
          }
          columns={["Stage", "Reached", "Still here", "Conversion"]}
          tableRows={
            anyReached
              ? funnel.map((s) => [
                  STAGE_LABELS[s.stage],
                  s.reached,
                  s.still_pending,
                  s.conversion_to_next != null ? fmtPct(s.conversion_to_next) : "—",
                ])
              : []
          }
          empty="No stage events yet — log a few applications first."
        >
          <BarRows rows={funnelRows} />
        </ChartCard>

        <ChartCard
          title="Time between stages"
          sub="Average days each transition takes, from the event timestamps."
          columns={["Transition", "Avg days", "Count"]}
          tableRows={slowestFirst.map((t) => [
            `${STAGE_LABELS[t.from_stage]} → ${STAGE_LABELS[t.to_stage]}`,
            fmtDays(t.avg_days),
            t.transitions,
          ])}
          empty="Needs at least one application with two events."
        >
          <BarRows rows={timeRows} />
        </ChartCard>

        <ChartCard
          title="Response rate by source"
          sub="A response is anything beyond the initial application — including a rejection."
          columns={["Source", "Rate", "Responded", "Total"]}
          tableRows={bySource.map((s) => [
            SOURCE_LABELS[s.source],
            fmtPct(s.response_rate),
            s.responded,
            s.total,
          ])}
          empty="No applications yet."
        >
          <BarRows rows={sourceRows} />
        </ChartCard>

        <ChartCard
          title="Current stage mix"
          sub="Where every application sits right now."
          columns={["Stage", "Applications"]}
          tableRows={byStage.map((s) => [STAGE_LABELS[s.stage], s.count])}
          empty="No applications yet."
        >
          <BarRows rows={mixRows} />
        </ChartCard>
      </div>
    </main>
  );
}
