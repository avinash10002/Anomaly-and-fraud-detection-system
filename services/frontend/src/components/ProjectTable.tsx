"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import { getDistricts, getProjects } from "@/lib/api";
import { formatINR } from "@/lib/format";
import type { ProjectType, ProjectWithRisk, RiskLevel } from "@/lib/types";

const TYPES: ProjectType[] = ["road", "building", "park", "other"];
const RISKS: RiskLevel[] = ["low", "medium", "high"];

export function ProjectTable() {
  const [projects, setProjects] = useState<ProjectWithRisk[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [district, setDistrict] = useState("");
  const [type, setType] = useState("");
  const [riskLevel, setRiskLevel] = useState<RiskLevel | "">("");
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [d] = await Promise.all([getDistricts()]);
      if (!cancelled) setDistricts(d);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    startTransition(() => {
      void (async () => {
        const list = await getProjects({
          district: district || undefined,
          type: type || undefined,
          riskLevel: riskLevel || undefined,
        });
        if (!cancelled) {
          setProjects(list);
          setLoading(false);
        }
      })();
    });
    return () => {
      cancelled = true;
    };
  }, [district, type, riskLevel]);

  const summary = useMemo(() => {
    const high = projects.filter((p) => p.riskLevel === "high").length;
    const mid = projects.filter((p) => p.riskLevel === "medium").length;
    return { high, mid, total: projects.length };
  }, [projects]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">
            Projects dashboard
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Risk badges use each project&apos;s highest anomaly score
            (green&nbsp;&lt;0.3, amber&nbsp;0.3–0.7, red&nbsp;&gt;0.7).
          </p>
        </div>
        <p className="text-sm text-ink-muted">
          Showing <strong className="text-ink">{summary.total}</strong>
          {" · "}
          <span className="text-risk-high">{summary.high} high</span>
          {" · "}
          <span className="text-risk-mid">{summary.mid} medium</span>
        </p>
      </div>

      <div className="panel grid gap-3 p-4 sm:grid-cols-3">
        <label>
          <span className="field-label">District</span>
          <select
            className="field-control"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
          >
            <option value="">All districts</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Project type</span>
          <select
            className="field-control"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">All types</option>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Risk level</span>
          <select
            className="field-control"
            value={riskLevel}
            onChange={(e) => setRiskLevel(e.target.value as RiskLevel | "")}
          >
            <option value="">All risk levels</option>
            {RISKS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={`panel overflow-hidden ${isPending || loading ? "opacity-70" : ""}`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-surface-soft text-[11px] uppercase tracking-wide text-ink-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Project</th>
                <th className="px-4 py-3 font-semibold">District</th>
                <th className="px-4 py-3 font-semibold">Type</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Cost</th>
                <th className="px-4 py-3 font-semibold">Risk</th>
                <th className="px-4 py-3 font-semibold">Flags</th>
              </tr>
            </thead>
            <tbody>
              {loading && projects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-ink-muted">
                    Loading projects…
                  </td>
                </tr>
              ) : projects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-ink-muted">
                    No projects match the selected filters.
                  </td>
                </tr>
              ) : (
                projects.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50/80"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/${p.id}`}
                        className="font-medium text-brand hover:underline"
                      >
                        {p.title}
                      </Link>
                      <div className="mt-0.5 text-xs text-ink-muted">
                        MP: {p.mpName}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{p.district}</td>
                    <td className="px-4 py-3 capitalize">{p.type}</td>
                    <td className="px-4 py-3 capitalize">{p.status}</td>
                    <td className="px-4 py-3 tabular-nums">{formatINR(p.cost)}</td>
                    <td className="px-4 py-3">
                      <RiskBadge level={p.riskLevel} score={p.riskScore} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{p.anomalyCount}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
