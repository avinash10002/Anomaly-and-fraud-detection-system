"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";
import { RiskBadge } from "@/components/RiskBadge";
import {
  PROJECT_CATEGORIES,
  getAdministrativeHierarchy,
  getDashboardStats,
  getProjects,
} from "@/lib/api";
import { formatINR } from "@/lib/format";
import { useRole } from "@/lib/role-context";
import type {
  AdministrativeHierarchy,
  DashboardStats,
  ProjectWithRisk,
  RiskLevel,
} from "@/lib/types";

const STATUSES = ["ongoing", "completed", "stalled", "planned"];
const RISKS: RiskLevel[] = ["low", "medium", "high"];
const SEARCH_DEBOUNCE_MS = 300;
const PAGE_SIZE = 20;

export function ProjectTable() {
  const { role, isCitizen } = useRole();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [adminData, setAdminData] = useState<AdministrativeHierarchy>({
    states: [],
    constituenciesByState: {},
  });

  const [projects, setProjects] = useState<ProjectWithRisk[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  // Filters
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedState, setSelectedState] = useState("");
  const [selectedConstituency, setSelectedConstituency] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [selectedRisk, setSelectedRisk] = useState<RiskLevel | "">("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [adm, st] = await Promise.all([
          getAdministrativeHierarchy(),
          getDashboardStats(role),
        ]);
        if (!cancelled) {
          setAdminData(adm);
          setStats(st);
        }
      } catch {
        if (!cancelled) {
          setAdminData({ states: [], constituenciesByState: {} });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [role]);

  const availableConstituencies = useMemo(() => {
    if (!selectedState) {
      const all = Object.values(adminData.constituenciesByState).flat();
      return Array.from(new Set(all)).sort();
    }
    return adminData.constituenciesByState[selectedState] || [];
  }, [selectedState, adminData]);

  const handleStateChange = (newState: string) => {
    setSelectedState(newState);
    setPage(1);
    if (newState && adminData.constituenciesByState[newState]) {
      if (!adminData.constituenciesByState[newState].includes(selectedConstituency)) {
        setSelectedConstituency("");
      }
    } else if (newState) {
      setSelectedConstituency("");
    }
  };

  // Reset to page 1 whenever filters change
  useEffect(() => {
    setPage(1);
  }, [
    selectedState,
    selectedConstituency,
    selectedCategory,
    selectedStatus,
    selectedRisk,
    debouncedSearch,
    role,
  ]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    startTransition(() => {
      void (async () => {
        const result = await getProjects(
          {
            state: selectedState || undefined,
            constituency: selectedConstituency || undefined,
            category: selectedCategory || undefined,
            status: selectedStatus || undefined,
            riskLevel: selectedRisk || undefined,
            search: debouncedSearch || undefined,
          },
          role,
          page,
          PAGE_SIZE
        );
        if (!cancelled) {
          setProjects(result.data);
          setTotal(result.total);
          setLoading(false);
        }
      })();
    });
    return () => {
      cancelled = true;
    };
  }, [
    selectedState,
    selectedConstituency,
    selectedCategory,
    selectedStatus,
    selectedRisk,
    debouncedSearch,
    role,
    page,
  ]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const rangeStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, total);

  const hasActiveFilters = Boolean(
    search ||
      selectedState ||
      selectedConstituency ||
      selectedCategory ||
      selectedStatus ||
      selectedRisk
  );

  const clearFilters = () => {
    setSearch("");
    setDebouncedSearch("");
    setSelectedState("");
    setSelectedConstituency("");
    setSelectedCategory("");
    setSelectedStatus("");
    setSelectedRisk("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="panel p-4">
            <span className="field-label">Total Projects</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="font-display text-2xl font-bold text-ink">
                {stats.totalProjects.toLocaleString()}
              </span>
              <span className="text-xs text-ink-muted">Monitored works</span>
            </div>
          </div>

          <div className="panel p-4">
            <span className="field-label">Total Allocation</span>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="font-display text-2xl font-bold text-ink">
                {formatINR(stats.totalAllocation)}
              </span>
              <span className="text-xs text-ink-muted">Sanctioned</span>
            </div>
          </div>

          <div className="panel p-4">
            <span className="field-label">Status Breakdown</span>
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
              <span className="rounded bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">
                {stats.statusDistribution.completed || 0} completed
              </span>
              <span className="rounded bg-blue-50 px-2 py-0.5 font-medium text-blue-700">
                {stats.statusDistribution.ongoing || 0} ongoing
              </span>
              <span className="rounded bg-rose-50 px-2 py-0.5 font-medium text-rose-700">
                {stats.statusDistribution.stalled || 0} stalled
              </span>
            </div>
          </div>

          <div className="panel p-4">
            <span className="field-label">Risk Distribution</span>
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
              <span className="rounded bg-red-50 px-2 py-0.5 font-semibold text-risk-high">
                {stats.riskDistribution.high || 0} High
              </span>
              <span className="rounded bg-amber-50 px-2 py-0.5 font-semibold text-risk-mid">
                {stats.riskDistribution.medium || 0} Med
              </span>
              <span className="rounded bg-emerald-50 px-2 py-0.5 font-semibold text-risk-low">
                {stats.riskDistribution.low || 0} Low
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">
              MPLADS Works Explorer
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              {isCitizen
                ? "Public view: Browse developmental works by state, constituency, and risk categories."
                : "Official audit view: Inspect high-risk anomalies, cross-engine signals, and sanction records."}
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <span>
              Showing{" "}
              <strong className="text-ink">
                {rangeStart}–{rangeEnd}
              </strong>{" "}
              of <strong className="text-ink">{total}</strong>
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-xs font-medium text-brand hover:underline"
              >
                Clear all filters
              </button>
            )}
          </div>
        </div>

        <div className="panel p-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by WORK description, sanction title, or keywords..."
                className="field-control pl-9 text-sm"
              />
              <svg
                className="absolute left-3 top-2.5 h-4 w-4 text-ink-muted"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          </div>

          <div className="mt-3 grid gap-2.5 sm:grid-cols-2 md:grid-cols-5">
            <label>
              <span className="field-label">State</span>
              <select
                className="field-control text-xs"
                value={selectedState}
                onChange={(e) => handleStateChange(e.target.value)}
              >
                <option value="">All States</option>
                {adminData.states.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="field-label">Constituency</span>
              <select
                className="field-control text-xs"
                value={selectedConstituency}
                onChange={(e) => {
                  setSelectedConstituency(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Constituencies</option>
                {availableConstituencies.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="field-label">Category</span>
              <select
                className="field-control text-xs"
                value={selectedCategory}
                onChange={(e) => {
                  setSelectedCategory(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Categories</option>
                {PROJECT_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="field-label">Status</span>
              <select
                className="field-control text-xs"
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Statuses</option>
                {STATUSES.map((st) => (
                  <option key={st} value={st} className="capitalize">
                    {st}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="field-label">Risk Level</span>
              <select
                className="field-control text-xs"
                value={selectedRisk}
                onChange={(e) => {
                  setSelectedRisk(e.target.value as RiskLevel | "");
                  setPage(1);
                }}
              >
                <option value="">All Risk Levels</option>
                {RISKS.map((r) => (
                  <option key={r} value={r} className="capitalize">
                    {r}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      <div className={`panel overflow-hidden ${isPending || loading ? "opacity-70" : ""}`}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-surface-soft text-[11px] uppercase tracking-wide text-ink-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Work / Project</th>
                <th className="px-4 py-3 font-semibold">Location</th>
                <th className="px-4 py-3 font-semibold">Category</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Allocation</th>
                <th className="px-4 py-3 font-semibold">Risk Level</th>
                <th className="px-4 py-3 font-semibold">Flags</th>
              </tr>
            </thead>
            <tbody>
              {loading && projects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-ink-muted">
                    Loading MPLADS projects…
                  </td>
                </tr>
              ) : projects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-ink-muted">
                    No projects found matching the specified filters.
                  </td>
                </tr>
              ) : (
                projects.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50/80 transition-colors"
                  >
                    <td className="px-4 py-3 max-w-sm">
                      <div className="flex items-center gap-1.5">
                        <Link
                          href={`/dashboard/${p.id}`}
                          className="font-medium text-brand hover:underline line-clamp-1"
                          title={p.title}
                        >
                          {p.title}
                        </Link>
                        {p.sourceType === "DEMO_SYNTHETIC" && (
                          <span className="shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold tracking-tight text-amber-800 border border-amber-300">
                            DEMO
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 text-xs text-ink-muted line-clamp-1">
                        MP: {p.mpName} {p.contractorName ? `· ${p.contractorName}` : ""}
                      </div>
                    </td>

                    <td className="px-4 py-3 text-xs text-ink-muted whitespace-nowrap">
                      <div className="font-medium text-ink">
                        {p.constituency || p.district}
                      </div>
                      <div>{p.state || "—"}</div>
                    </td>

                    <td className="px-4 py-3 text-xs whitespace-nowrap">
                      {p.category || p.type}
                    </td>

                    <td className="px-4 py-3 text-xs capitalize whitespace-nowrap">
                      <span
                        className={`inline-block rounded px-2 py-0.5 font-medium ${
                          p.status === "completed"
                            ? "bg-emerald-50 text-emerald-700"
                            : p.status === "stalled"
                            ? "bg-rose-50 text-rose-700"
                            : "bg-blue-50 text-blue-700"
                        }`}
                      >
                        {p.status}
                      </span>
                    </td>

                    <td className="px-4 py-3 text-xs font-medium tabular-nums whitespace-nowrap">
                      {formatINR(p.cost)}
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <RiskBadge level={p.riskLevel} score={p.riskScore} />
                    </td>

                    <td className="px-4 py-3 text-xs tabular-nums text-center">
                      <span
                        className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold ${
                          p.anomalyCount > 0
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {p.anomalyCount}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-surface-soft px-4 py-3">
          <p className="text-xs text-ink-muted">
            Page <strong className="text-ink">{page}</strong> of{" "}
            <strong className="text-ink">{totalPages}</strong>
            <span className="mx-1.5 text-slate-300">·</span>
            {PAGE_SIZE} entries per page
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
