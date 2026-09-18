import type { RiskLevel } from "@/lib/types";

const RISK_STYLES: Record<
  RiskLevel,
  { badge: string; dot: string; label: string }
> = {
  low: {
    badge: "bg-emerald-50 text-risk-low ring-1 ring-emerald-200",
    dot: "bg-risk-low",
    label: "Low",
  },
  medium: {
    badge: "bg-amber-50 text-risk-mid ring-1 ring-amber-200",
    dot: "bg-risk-mid",
    label: "Medium",
  },
  high: {
    badge: "bg-red-50 text-risk-high ring-1 ring-red-200",
    dot: "bg-risk-high",
    label: "High",
  },
};

export function RiskBadge({
  level,
  score,
  compact = false,
}: {
  level: RiskLevel;
  score?: number;
  compact?: boolean;
}) {
  const style = RISK_STYLES[level];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-semibold tracking-wide ${style.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-sm ${style.dot}`} aria-hidden />
      {style.label}
      {!compact && typeof score === "number" ? (
        <span className="font-normal opacity-80">{Math.round(score * 100)}%</span>
      ) : null}
    </span>
  );
}

export function riskMarkerColor(level: RiskLevel): string {
  if (level === "high") return "#c0392b";
  if (level === "medium") return "#b8860b";
  return "#1e7a46";
}
