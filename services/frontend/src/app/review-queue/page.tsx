"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import { useRole } from "@/lib/role-context";
import {
  getPendingAnomalyFlags,
  getProjectTitleSync,
  scoreToRiskLevel,
  updateAnomalyReviewStatus,
} from "@/lib/api";
import { formatPercent } from "@/lib/format";
import type { AnomalyFlag } from "@/lib/types";

export default function ReviewQueuePage() {
  const { isOfficial, official, loading: authLoading } = useRole();
  const [flags, setFlags] = useState<AnomalyFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const list = await getPendingAnomalyFlags();
    setFlags(list);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleReview(
    id: string,
    status: "confirmed" | "dismissed"
  ) {
    setBusyId(id);
    await updateAnomalyReviewStatus(id, status);
    setFlags((prev) => prev.filter((f) => f.id !== id));
    setBusyId(null);
    setToast(status === "confirmed" ? "Flag confirmed" : "Flag dismissed");
    window.setTimeout(() => setToast(null), 2000);
  }

  return (
    <div className="space-y-4">
      {!authLoading && !isOfficial && (
        <div className="panel p-4 border-amber-300 bg-amber-50/90 flex flex-wrap items-center justify-between gap-3 text-xs text-amber-900">
          <div className="flex items-center gap-2">
            <span className="text-base">🔒</span>
            <span>
              <strong>Official Login Required:</strong> To review and act on pending flags as a verified official, please sign in with your pre-registered email.
            </span>
          </div>
          <Link
            href="/login?redirect=/review-queue"
            className="btn btn-primary text-xs py-1 px-3 shrink-0"
          >
            Sign In with Email
          </Link>
        </div>
      )}

      {official && (
        <div className="panel p-3 bg-blue-50/70 border-blue-200 flex items-center justify-between text-xs text-blue-950">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span>
              Logged in as <strong>{official.name}</strong> ({official.email}) •{" "}
              <span className="font-semibold uppercase text-brand tracking-wider">{official.role}</span>
            </span>
          </div>
          <span className="text-[11px] text-blue-800/80">Audit actions will be attributed to this account</span>
        </div>
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">
            Review queue
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Pending anomaly flags. Confirm or dismiss updates local mock state
            only.
          </p>
        </div>
        <p className="text-sm text-ink-muted">
          <strong className="text-ink">{flags.length}</strong> pending
        </p>
      </div>

      {toast ? (
        <div
          className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-risk-low"
          role="status"
        >
          {toast}
        </div>
      ) : null}

      {loading ? (
        <div className="panel px-4 py-10 text-center text-sm text-ink-muted">
          Loading queue…
        </div>
      ) : flags.length === 0 ? (
        <div className="panel px-4 py-10 text-center text-sm text-ink-muted">
          Queue is empty. No pending flags.
        </div>
      ) : (
        <ul className="space-y-3">
          {flags.map((flag) => (
            <li key={flag.id} className="panel p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-surface-soft px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      {flag.sourceEngine}
                    </span>
                    <RiskBadge
                      level={scoreToRiskLevel(flag.score)}
                      score={flag.score}
                    />
                    <span className="text-sm font-semibold tabular-nums">
                      {formatPercent(flag.score)}
                    </span>
                  </div>
                  <Link
                    href={`/dashboard/${flag.projectId}`}
                    className="block text-sm font-semibold text-brand hover:underline"
                  >
                    {getProjectTitleSync(flag.projectId)}
                  </Link>
                  <p className="text-sm leading-relaxed text-ink">
                    {flag.reasonText}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    className="btn-success"
                    disabled={busyId === flag.id}
                    onClick={() => void handleReview(flag.id, "confirmed")}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    className="btn-danger"
                    disabled={busyId === flag.id}
                    onClick={() => void handleReview(flag.id, "dismissed")}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
