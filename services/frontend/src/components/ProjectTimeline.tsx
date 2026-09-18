import type { AnomalyFlag } from "@/lib/types";
import { formatDate } from "@/lib/format";

type TimelineEvent = {
  id: string;
  label: string;
  date: string;
  kind: "sanction" | "completion" | "flag";
};

export function ProjectTimeline({
  sanctionDate,
  completionDate,
  flags,
}: {
  sanctionDate: string;
  completionDate: string | null;
  flags: AnomalyFlag[];
}) {
  const events: TimelineEvent[] = [
    {
      id: "sanction",
      label: "Sanctioned",
      date: sanctionDate,
      kind: "sanction",
    },
    ...flags.map((f) => ({
      id: f.id,
      label: `Flag raised (${f.sourceEngine})`,
      date: f.flaggedAt,
      kind: "flag" as const,
    })),
  ];

  if (completionDate) {
    events.push({
      id: "completion",
      label: "Declared complete",
      date: completionDate,
      kind: "completion",
    });
  }

  events.sort((a, b) => a.date.localeCompare(b.date));

  return (
    <ol className="relative space-y-0 border-l border-slate-300 pl-5">
      {events.map((event, idx) => (
        <li key={event.id} className="relative pb-5 last:pb-0">
          <span
            className={`absolute -left-[1.4rem] top-1 h-2.5 w-2.5 rounded-sm ring-4 ring-white ${
              event.kind === "flag"
                ? "bg-risk-high"
                : event.kind === "completion"
                  ? "bg-risk-low"
                  : "bg-brand"
            }`}
            aria-hidden
          />
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <time className="text-xs font-semibold tabular-nums text-ink-muted">
              {formatDate(event.date)}
            </time>
            <span className="text-sm font-medium text-ink">{event.label}</span>
          </div>
          {idx < events.length - 1 ? null : null}
        </li>
      ))}
    </ol>
  );
}
