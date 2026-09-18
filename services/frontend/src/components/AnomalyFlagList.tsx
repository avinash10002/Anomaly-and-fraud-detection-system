import { RiskBadge } from "@/components/RiskBadge";
import type { AnomalyFlag } from "@/lib/types";
import { formatDate, formatPercent } from "@/lib/format";

export function AnomalyFlagList({ flags }: { flags: AnomalyFlag[] }) {
  if (!flags.length) {
    return (
      <p className="rounded border border-dashed border-slate-300 bg-surface-soft px-4 py-8 text-center text-sm text-ink-muted">
        No anomaly flags for this project.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {flags.map((flag) => (
        <li key={flag.id} className="panel p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-surface-soft px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                {flag.sourceEngine}
              </span>
              <span className="rounded bg-surface-soft px-2 py-0.5 text-xs font-medium capitalize text-ink">
                {flag.reviewStatus}
              </span>
              <span className="text-xs text-ink-muted">
                {formatDate(flag.flaggedAt)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <RiskBadge
                level={
                  flag.score > 0.7 ? "high" : flag.score >= 0.3 ? "medium" : "low"
                }
                score={flag.score}
              />
              <span className="text-sm font-semibold tabular-nums text-ink">
                {formatPercent(flag.score)}
              </span>
            </div>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-ink">{flag.reasonText}</p>
        </li>
      ))}
    </ul>
  );
}
