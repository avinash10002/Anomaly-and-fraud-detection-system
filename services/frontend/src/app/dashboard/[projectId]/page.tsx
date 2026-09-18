"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import {
  getProjectById,
  updateAnomalyReviewStatus,
} from "@/lib/api";
import { formatDate, formatINR, formatPercent } from "@/lib/format";
import { useRole } from "@/lib/role-context";
import type { AnomalyFlag, ProjectDetail } from "@/lib/types";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;
  const { role, isCitizen, isOfficial } = useRole();

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyFlagId, setBusyFlagId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      const data = await getProjectById(projectId, role);
      if (!cancelled) {
        setProject(data);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, role]);

  const handleReviewAction = async (
    flagId: string,
    reviewStatus: "confirmed" | "dismissed"
  ) => {
    setBusyFlagId(flagId);
    const notes = reviewNotes[flagId] || "";
    const updated = await updateAnomalyReviewStatus(flagId, reviewStatus, notes);

    if (updated && project) {
      setProject({
        ...project,
        flags: project.flags?.map((f) => (f.id === flagId ? { ...f, reviewStatus, reviewerNotes: notes } : f)),
      });
      setToast(
        reviewStatus === "confirmed"
          ? "Anomaly flag confirmed and audit logged."
          : "Anomaly flag dismissed."
      );
      setTimeout(() => setToast(null), 3000);
    }
    setBusyFlagId(null);
  };

  if (loading) {
    return (
      <div className="panel p-12 text-center text-sm text-ink-muted">
        Loading project details…
      </div>
    );
  }

  if (!project) {
    return (
      <div className="panel p-12 text-center space-y-4">
        <p className="text-base text-ink">Project not found.</p>
        <Link href="/dashboard" className="text-sm font-medium text-brand hover:underline">
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  const isDemo =
    project.sourceType === "DEMO_SYNTHETIC" ||
    project.inspectionCaptures?.some((c) => c.sourceType === "DEMO_SYNTHETIC") ||
    project.flags?.some((f) => f.reasonText.includes("DEMO_SYNTHETIC"));

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* ── Top Navigation & Title Header ─────────────────────────────── */}
      <div>
        <Link
          href="/dashboard"
          className="text-sm font-medium text-brand hover:underline"
        >
          ← Back to dashboard
        </Link>

        {toast && (
          <div className="mt-3 rounded border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm text-emerald-800 font-medium">
            {toast}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2">
              <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">
                {project.title}
              </h1>
              {isDemo && (
                <span className="shrink-0 rounded bg-amber-100 border border-amber-300 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-amber-900">
                  DEMO SYNTHETIC
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-ink-muted">
              {project.constituency || project.district}
              {project.state ? `, ${project.state}` : ""} · MP: {project.mpName} · Contractor:{" "}
              {project.contractorName}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <RiskBadge level={project.riskLevel} score={project.riskScore} />
          </div>
        </div>
      </div>

      {/* ── Basic Sanction & Meta Card ────────────────────────────────── */}
      <section className="panel grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Info label="Category" value={project.category || project.type} capitalize />
        <Info label="Status" value={project.status} capitalize />
        <Info label="Sanctioned Allocation" value={formatINR(project.cost)} />
        <Info label="Sanction Date" value={formatDate(project.sanctionDate)} />
        <Info
          label="Completion Date"
          value={project.completionDate ? formatDate(project.completionDate) : "In Progress / Stalled"}
        />
        <Info label="District / State" value={`${project.district}, ${project.state || "India"}`} />
        <Info
          label="Coordinates"
          value={
            project.lat && project.lng
              ? `${project.lat.toFixed(4)}, ${project.lng.toFixed(4)} ${
                  isDemo ? "(Synthetic Demo)" : ""
                }`
              : "Administrative Record Only (No GPS)"
          }
        />
        <Info label="Anomaly Count" value={String(project.anomalyCount)} />
      </section>

      {/* ── SECTION 1: FINANCIAL ANALYSIS ─────────────────────────────── */}
      <section className="panel p-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-blue-100 text-blue-800 text-xs font-bold">
              ₹
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">
              Financial Analysis
            </h2>
          </div>
          <span className="text-xs text-ink-muted font-medium">
            Engine: cost-estimator & financial benchmarks
          </span>
        </div>

        {project.financialAnalysis ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-md border border-slate-200 bg-slate-50/50 p-3">
                <span className="field-label">Sanctioned Amount</span>
                <p className="mt-1 text-base font-bold text-ink">
                  {formatINR(project.financialAnalysis.allocation)}
                </p>
              </div>

              <div className="rounded-md border border-slate-200 bg-slate-50/50 p-3">
                <span className="field-label">Estimated Range</span>
                <p className="mt-1 text-sm font-semibold text-ink">
                  {formatINR(project.financialAnalysis.estimatedMin)} –{" "}
                  {formatINR(project.financialAnalysis.estimatedMax)}
                </p>
                <p className="text-[11px] text-ink-muted">Expected benchmark envelope</p>
              </div>

              <div className="rounded-md border border-slate-200 bg-slate-50/50 p-3">
                <span className="field-label">Category Median</span>
                <p className="mt-1 text-sm font-semibold text-ink">
                  {formatINR(project.financialAnalysis.categoryMedian)}
                </p>
                <p className="text-[11px] text-ink-muted">State baseline median</p>
              </div>

              <div
                className={`rounded-md border p-3 ${
                  project.financialAnalysis.deviationPercent > 50
                    ? "border-red-200 bg-red-50/60"
                    : "border-slate-200 bg-slate-50/50"
                }`}
              >
                <span className="field-label">Deviation</span>
                <p
                  className={`mt-1 text-base font-bold ${
                    project.financialAnalysis.deviationPercent > 50
                      ? "text-red-700"
                      : "text-ink"
                  }`}
                >
                  +{project.financialAnalysis.deviationPercent.toFixed(1)}%
                </p>
                <p className="text-[11px] text-ink-muted">Above expected norms</p>
              </div>
            </div>

            <div className="rounded-md border border-slate-200 bg-white p-3 text-sm">
              <span className="font-semibold text-ink">Audit Rationale: </span>
              <span className="text-slate-700">{project.financialAnalysis.deviationReason}</span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-muted">Financial baseline data not recorded.</p>
        )}
      </section>

      {/* ── SECTION 2: SIMILAR PROJECTS (NLP SIMILARITY) ──────────────── */}
      <section className="panel p-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-purple-100 text-purple-800 text-xs font-bold">
              NLP
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">
              Similar Projects (NLP Similarity Engine)
            </h2>
          </div>
          <span className="text-xs text-ink-muted font-medium">
            Semantic description overlap analysis
          </span>
        </div>

        {project.similarProjects && project.similarProjects.length > 0 ? (
          <div className="space-y-3">
            {project.similarProjects.map((sp) => (
              <div
                key={sp.projectId}
                className="rounded-lg border border-purple-200 bg-purple-50/30 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-sm text-purple-950">
                    {sp.title}
                  </span>
                  <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-bold text-purple-800">
                    {formatPercent(sp.similarityScore)} similarity
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-700 leading-relaxed">
                  <strong className="text-ink">Overlap Flag:</strong> {sp.overlapReason}
                </p>
                <div className="mt-2 flex items-center gap-3 text-[11px] text-ink-muted">
                  <span>Location: {sp.constituency || sp.state || "Same region"}</span>
                  <span>·</span>
                  <Link
                    href={`/dashboard/${sp.projectId}`}
                    className="font-medium text-brand hover:underline"
                  >
                    View matching project record →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded border border-dashed border-slate-200 bg-slate-50 p-4 text-center text-xs text-ink-muted">
            No duplicate or suspiciously overlapping work scopes detected across the state repository.
          </p>
        )}
      </section>

      {/* ── SECTION 3: IMAGE INSPECTION & CHRONOLOGICAL TIMELINE ──────── */}
      <section className="panel p-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-emerald-100 text-emerald-800 text-xs font-bold">
              IMG
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">
              Image Inspection Timeline
            </h2>
          </div>
          <span className="text-xs text-ink-muted font-medium">
            Computer vision defect detection
          </span>
        </div>

        {/* HIGH-VISIBILITY DEMO/SYNTHETIC BADGE */}
        {isDemo && (
          <div className="mb-4 rounded-lg border-2 border-amber-400 bg-amber-50 p-3.5 shadow-sm">
            <div className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-500 text-white font-bold text-xs">
                !
              </span>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900">
                  DEMO / SYNTHETIC DATA
                </h4>
                <p className="mt-0.5 text-xs text-amber-800 leading-relaxed">
                  This inspection timeline and degradation milestones are <strong>synthetically seeded</strong> for interactive evaluation. Real MPLADS records in production are verified against official geo-tagged site images.
                </p>
              </div>
            </div>
          </div>
        )}

        {project.inspectionCaptures && project.inspectionCaptures.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {project.inspectionCaptures.map((capture, idx) => {
              const sevColors = {
                none: "bg-emerald-50 text-emerald-700 border-emerald-200",
                minor: "bg-amber-50 text-amber-700 border-amber-200",
                moderate: "bg-orange-50 text-orange-700 border-orange-200",
                severe: "bg-red-50 text-red-700 border-red-200",
              }[capture.defectSeverity];

              return (
                <div
                  key={capture.id || idx}
                  className="relative flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-3.5 shadow-sm"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2 mb-2">
                      <span className="text-xs font-semibold text-ink">
                        Capture #{idx + 1}
                      </span>
                      <span className="text-[11px] text-ink-muted">
                        {formatDate(capture.captureDate)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-xs font-medium text-slate-800">
                        {capture.label}
                      </span>
                      <span
                        className={`rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${sevColors}`}
                      >
                        {capture.defectSeverity}
                      </span>
                    </div>

                    {/* Image Preview Placeholder Box */}
                    <div className="my-2 flex h-24 w-full items-center justify-center rounded bg-slate-100 border border-slate-200 text-ink-muted text-xs text-center p-2">
                      <span>
                        📸 {capture.label}
                        <br />
                        <span className="text-[10px] opacity-75">
                          Resolution 1920x1080 · Geo-tagged
                        </span>
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">
                      {capture.defectDescription}
                    </p>
                  </div>

                  {capture.sourceType === "DEMO_SYNTHETIC" && (
                    <div className="mt-3 border-t border-slate-100 pt-2 text-[10px] font-semibold text-amber-800">
                      SYNTHETIC TIMELINE EVENT
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-ink-muted">No site inspection captures available.</p>
        )}
      </section>

      {/* ── SECTION 4: RISK ANALYSIS ──────────────────────────────────── */}
      <section className="panel p-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-red-100 text-red-800 text-xs font-bold">
              AI
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">
              Multi-Engine Risk Analysis
            </h2>
          </div>
          <RiskBadge level={project.riskLevel} score={project.riskScore} />
        </div>

        {project.riskBreakdown && (
          <div className="space-y-4">
            {isCitizen ? (
              <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-xs text-ink leading-relaxed">
                <span className="font-semibold text-ink">Public Risk Category: </span>
                <span className="capitalize font-medium text-slate-800">{project.riskLevel} Risk</span>
                <p className="mt-1 text-ink-muted">
                  {project.riskBreakdown.rationale}
                </p>
                <p className="mt-2 text-[11px] text-slate-500 italic">
                  Note: Raw algorithm weights and internal review credentials are restricted to authorized audit officials.
                </p>
              </div>
            ) : (
              <div>
                <p className="text-xs text-ink-muted mb-3">
                  Comprehensive breakdown synthesized across Financial, NLP Semantic, and Computer Vision engines:
                </p>

                <div className="grid gap-3 sm:grid-cols-3">
                  {/* Financial Engine Factor */}
                  <div className="rounded-md border border-slate-200 bg-white p-3">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-medium text-ink">Financial Flag Signal</span>
                      <span className="font-bold text-ink">
                        {formatPercent(project.riskBreakdown.financialScore)}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full bg-blue-600 rounded-full"
                        style={{ width: `${project.riskBreakdown.financialScore * 100}%` }}
                      />
                    </div>
                    <span className="mt-1.5 block text-[10px] text-ink-muted">
                      Cost outlier vs schedule benchmarks
                    </span>
                  </div>

                  {/* NLP Engine Factor */}
                  <div className="rounded-md border border-slate-200 bg-white p-3">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-medium text-ink">NLP Duplication Signal</span>
                      <span className="font-bold text-ink">
                        {formatPercent(project.riskBreakdown.nlpScore)}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full bg-purple-600 rounded-full"
                        style={{ width: `${project.riskBreakdown.nlpScore * 100}%` }}
                      />
                    </div>
                    <span className="mt-1.5 block text-[10px] text-ink-muted">
                      Semantic scope repetition check
                    </span>
                  </div>

                  {/* Image Engine Factor */}
                  <div className="rounded-md border border-slate-200 bg-white p-3">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-medium text-ink">Image Defect Signal</span>
                      <span className="font-bold text-ink">
                        {formatPercent(project.riskBreakdown.imageScore)}
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full bg-emerald-600 rounded-full"
                        style={{ width: `${project.riskBreakdown.imageScore * 100}%` }}
                      />
                    </div>
                    <span className="mt-1.5 block text-[10px] text-ink-muted">
                      Chronological degradation severity
                    </span>
                  </div>
                </div>

                <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
                  <span className="font-semibold text-ink">Synthesized Rationale: </span>
                  <span className="text-slate-700">{project.riskBreakdown.rationale}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── SECTION 5: REVIEW ACTIONS (OFFICIALS ONLY) ─────────────────── */}
      {isOfficial && (
        <section className="panel p-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded bg-brand/10 text-brand-dark text-xs font-bold">
                ✓
              </span>
              <h2 className="font-display text-lg font-semibold text-ink">
                Review Actions & Audit Decisions
              </h2>
            </div>
            <span className="text-xs text-ink-muted font-medium">
              Official Workflow · Status updates persisted
            </span>
          </div>

          {project.flags && project.flags.length > 0 ? (
            <div className="space-y-4">
              {project.flags.map((flag) => (
                <div
                  key={flag.id}
                  className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-surface-soft px-2 py-0.5 text-xs font-semibold uppercase text-ink-muted">
                        {flag.sourceEngine}
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-bold capitalize ${
                          flag.reviewStatus === "confirmed"
                            ? "bg-red-50 text-red-700"
                            : flag.reviewStatus === "dismissed"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-700"
                        }`}
                      >
                        {flag.reviewStatus}
                      </span>
                      <span className="text-xs text-ink-muted">
                        Flagged {formatDate(flag.flaggedAt)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <RiskBadge
                        level={flag.score > 0.7 ? "high" : flag.score >= 0.3 ? "medium" : "low"}
                        score={flag.score}
                      />
                    </div>
                  </div>

                  <p className="text-xs text-ink leading-relaxed mb-3">
                    {flag.reasonText}
                  </p>

                  {/* Reviewer Note Input & Action Buttons */}
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2 border-t border-slate-100">
                    <input
                      type="text"
                      placeholder="Add official audit justification notes..."
                      value={reviewNotes[flag.id] || flag.reviewerNotes || ""}
                      onChange={(e) =>
                        setReviewNotes((prev) => ({ ...prev, [flag.id]: e.target.value }))
                      }
                      className="field-control flex-1 text-xs"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={busyFlagId === flag.id || flag.reviewStatus === "confirmed"}
                        onClick={() => handleReviewAction(flag.id, "confirmed")}
                        className="btn-danger text-xs px-3 py-1.5 disabled:opacity-50"
                      >
                        Confirm Flag
                      </button>
                      <button
                        type="button"
                        disabled={busyFlagId === flag.id || flag.reviewStatus === "dismissed"}
                        onClick={() => handleReviewAction(flag.id, "dismissed")}
                        className="btn-success text-xs px-3 py-1.5 disabled:opacity-50"
                      >
                        Dismiss Flag
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-ink-muted">No pending flags on this project record.</p>
          )}
        </section>
      )}
    </div>
  );
}

function Info({
  label,
  value,
  capitalize = false,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div>
      <dt className="field-label">{label}</dt>
      <dd className={`text-sm font-semibold text-ink ${capitalize ? "capitalize" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
