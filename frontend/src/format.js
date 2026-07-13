const dateFmt = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
});
const dateFmtYear = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const sameYear = d.getFullYear() === new Date().getFullYear();
  return (sameYear ? dateFmt : dateFmtYear).format(d);
}

export function daysSince(iso) {
  if (!iso) return null;
  return Math.max(0, Math.floor((Date.now() - new Date(iso)) / 86_400_000));
}

export function fmtDays(n) {
  if (n == null) return "—";
  const rounded = Math.round(n * 10) / 10;
  return `${rounded} ${rounded === 1 ? "day" : "days"}`;
}

export function fmtPct(fraction) {
  if (fraction == null) return "—";
  return `${Math.round(fraction * 100)}%`;
}
