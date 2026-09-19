import { MOCK_ANOMALIES, MOCK_IMAGES, MOCK_PROJECTS, replaceAnomalies } from "./mock-data";
import stateMediansRaw from "./state-medians.json";
import type {
  AdministrativeHierarchy,
  AnomalyFlag,
  AuditAssistantResponse,
  DashboardStats,
  FinancialAnalysis,
  InspectionCapture,
  Project,
  ProjectCitation,
  ProjectDetail,
  ProjectFilters,
  ProjectImage,
  ProjectListResult,
  ProjectType,
  ProjectWithRisk,
  ProjectRiskData,
  ReviewStatus,
  RiskBreakdown,
  RiskLevel,
  SimilarProject,
  StageIndicatorEntry,
  UserRole,
} from "./types";

/** Human-readable MPLADS-style categories derived from project type */
export const TYPE_TO_CATEGORY: Record<ProjectType, string> = {
  road: "Roads and Bridges",
  building: "Community Infrastructure",
  park: "Sports / Recreation",
  other: "Other Works",
};

export const PROJECT_CATEGORIES = [
  "Roads and Bridges",
  "Community Infrastructure",
  "Sports / Recreation",
  "Education",
  "Health",
  "Water and Sanitation",
  "Other Works",
] as const;

const CATEGORY_TO_TYPE: Record<string, ProjectType> = {
  "roads and bridges": "road",
  "community infrastructure": "building",
  "sports / recreation": "park",
  education: "building",
  health: "building",
  "water and sanitation": "other",
  "other works": "other",
  "normal/others": "other",
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8080/api/v1";

/** Simulated fallback delay for local mock data */
const MOCK_DELAY_MS = 20;

async function delay<T>(value: T): Promise<T> {
  if (MOCK_DELAY_MS <= 0) return value;
  await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
  return value;
}

export function scoreToRiskLevel(score: number): RiskLevel {
  if (score > 0.7) return "high";
  if (score >= 0.3) return "medium";
  return "low";
}

export function getProjectRiskScore(projectId: string, flags = MOCK_ANOMALIES): number {
  const scores = flags.filter((f) => f.projectId === projectId).map((f) => f.score);
  if (scores.length) return Math.max(...scores);
  const raw = MOCK_PROJECTS.find((p) => p.id === projectId);
  if (raw && raw.cost) {
    const benchmarksMap = stateMediansRaw as Record<string, { median: number; peerCount: number }>;
    const bench =
      (raw.state && raw.category && benchmarksMap[`${raw.state}::${raw.category}`]) ||
      (raw.state && benchmarksMap[`${raw.state}::Normal/Others`]);
    if (bench && bench.median > 0) {
      const mult = raw.cost / bench.median;
      if (mult >= 5.0) return Math.min(0.98, Math.max(0.88, 0.85 + (mult / 500.0) * 0.12));
      if (mult >= 3.0) return 0.75;
    }
  }
  return 0;
}

function withRisk(project: Project, flags = MOCK_ANOMALIES): ProjectWithRisk {
  const projectFlags = flags.filter((f) => f.projectId === project.id);
  let riskScore = projectFlags.length
    ? Math.max(...projectFlags.map((f) => f.score))
    : 0;

  if (riskScore === 0 && project.cost) {
    const benchmarksMap = stateMediansRaw as Record<string, { median: number; peerCount: number }>;
    const bench =
      (project.state && project.category && benchmarksMap[`${project.state}::${project.category}`]) ||
      (project.state && benchmarksMap[`${project.state}::Normal/Others`]);
    if (bench && bench.median > 0) {
      const mult = project.cost / bench.median;
      if (mult >= 5.0) {
        riskScore = Math.min(0.98, Math.max(0.88, 0.85 + (mult / 500.0) * 0.12));
      } else if (mult >= 3.0) {
        riskScore = 0.75;
      }
    }
  }

  const riskLevel = scoreToRiskLevel(riskScore);
  const anomalyCount = projectFlags.length > 0 ? projectFlags.length : riskLevel === "high" ? 1 : 0;

  return {
    ...project,
    riskScore,
    riskLevel,
    anomalyCount,
  };
}

// ── Mock enrichment (district → state/constituency) ─────────────────────────

const DEMO_PROJECT_IDS = new Set([
  "ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
  "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
  "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
  "b503d0a8-c311-5409-b365-5ade19ce3e2f",
  "e7becbea-467f-5e0d-a910-fe1e740972ba",
]);

const DISTRICT_META: Record<string, { state: string; constituency: string }> = {
  Churu: { state: "Rajasthan", constituency: "CHURU" },
  Dausa: { state: "Rajasthan", constituency: "Dausa" },
  Basti: { state: "Uttar Pradesh", constituency: "BASTI" },
  Gorakhpur: { state: "Uttar Pradesh", constituency: "GORAKHPUR" },
  Jamui: { state: "Bihar", constituency: "JAMUI(SC)" },
  Dewas: { state: "Madhya Pradesh", constituency: "DEWAS(SC)" },
  Rewa: { state: "Madhya Pradesh", constituency: "Rewa" },
  Satna: { state: "Madhya Pradesh", constituency: "Satna" },
  Sidhi: { state: "Madhya Pradesh", constituency: "Sidhi" },
  Nagpur: { state: "Maharashtra", constituency: "Nagpur South" },
};

function categoryFromType(type: ProjectType): string {
  return TYPE_TO_CATEGORY[type] || "Other Works";
}

function resolveCategory(raw: string | undefined, type: ProjectType): string {
  const cat = (raw || "").trim();
  if (!cat || cat.toLowerCase() === "normal/others") {
    return categoryFromType(type);
  }
  return cat;
}

function matchesCategoryFilter(
  project: { category?: string; type: ProjectType },
  filterCategory: string
): boolean {
  const wanted = filterCategory.toLowerCase();
  if ((project.category || "").toLowerCase() === wanted) return true;
  const mappedType = CATEGORY_TO_TYPE[wanted];
  return Boolean(mappedType && project.type === mappedType);
}

function enrichMockProject(p: Project): Project {
  const meta = DISTRICT_META[p.district];
  const type = p.type;
  return {
    ...p,
    state: p.state || meta?.state,
    constituency: p.constituency || meta?.constituency || p.district,
    category: resolveCategory(p.category, type),
    workDescription: p.workDescription || p.title,
    sourceType:
      p.sourceType ||
      (DEMO_PROJECT_IDS.has(p.id) ? "DEMO_SYNTHETIC" : "MPLADS_HISTORIC"),
  };
}

function buildMockHierarchy(): AdministrativeHierarchy {
  const constituenciesByState: Record<string, string[]> = {};
  for (const p of MOCK_PROJECTS.map(enrichMockProject)) {
    const st = p.state;
    const con = p.constituency;
    if (!st || !con) continue;
    if (!constituenciesByState[st]) constituenciesByState[st] = [];
    if (!constituenciesByState[st].includes(con)) {
      constituenciesByState[st].push(con);
    }
  }
  for (const st of Object.keys(constituenciesByState)) {
    constituenciesByState[st].sort();
  }
  return {
    states: Object.keys(constituenciesByState).sort(),
    constituenciesByState,
  };
}

function toCountRecord(
  items: Array<{ status?: string; level?: string; count: number }> | Record<string, number> | undefined,
  key: "status" | "level"
): Record<string, number> {
  if (!items) return {};
  if (!Array.isArray(items)) return items;
  const out: Record<string, number> = {};
  for (const item of items) {
    const k = (item[key] || "").toLowerCase();
    if (k) out[k] = item.count;
  }
  return out;
}

function normalizeHierarchy(raw: unknown): AdministrativeHierarchy {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const obj = raw as AdministrativeHierarchy;
    if (Array.isArray(obj.states) && obj.constituenciesByState) {
      return obj;
    }
  }
  if (Array.isArray(raw)) {
    const constituenciesByState: Record<string, string[]> = {};
    for (const entry of raw as Array<{
      state: string;
      constituencies?: Array<{ constituency: string } | string>;
    }>) {
      const names = (entry.constituencies || []).map((c) =>
        typeof c === "string" ? c : c.constituency
      );
      constituenciesByState[entry.state] = names.sort();
    }
    return {
      states: Object.keys(constituenciesByState).sort(),
      constituenciesByState,
    };
  }
  return buildMockHierarchy();
}

// ── Snake to Camel Mappers ──────────────────────────────────────────────────

function inferProjectType(item: any): ProjectType {
  if (item.type === "road" || item.type === "building" || item.type === "park" || item.type === "other") {
    return item.type;
  }
  const cat = String(item.category || item.title || item.work || "").toLowerCase();
  if (cat.includes("road") || cat.includes("bridge") || cat.includes("pathway") || cat.includes("flyover")) {
    return "road";
  }
  if (
    cat.includes("building") ||
    cat.includes("infra") ||
    cat.includes("sitting") ||
    cat.includes("school") ||
    cat.includes("health") ||
    cat.includes("stadium")
  ) {
    return "building";
  }
  if (cat.includes("sport") || cat.includes("park") || cat.includes("playfield") || cat.includes("recreation")) {
    return "park";
  }
  return "other";
}

function toCoord(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

function mapProjectSummary(item: any): ProjectWithRisk {
  const type = inferProjectType(item);
  return {
    id: item.id,
    title: item.title,
    type,
    sanctionDate: item.sanction_date || item.sanctionDate || "",
    completionDate: item.completion_date || item.completionDate || null,
    cost: item.allocation ?? item.cost ?? 0,
    lat: toCoord(item.lat),
    lng: toCoord(item.lng),
    district: item.district || "",
    state: item.state,
    constituency: item.constituency,
    workDescription: item.work_description || item.workDescription || item.work,
    category: resolveCategory(item.category, type),
    sourceType: item.source_type || item.sourceType,
    contractorName: item.contractor_name || item.contractorName || "Unassigned",
    mpName: item.mp_name || item.mpName || "Unassigned",
    status: (item.status?.toLowerCase() || "ongoing") as Project["status"],
    riskScore: item.risk_score ?? item.riskScore,
    riskLevel: (item.risk_level || item.riskLevel || "low") as RiskLevel,
    anomalyCount: item.anomaly_count ?? item.anomalyCount ?? 0,
  };
}

function mapProjectDetail(item: any): ProjectDetail {
  const base = mapProjectSummary(item);

  const financialAnalysis: FinancialAnalysis | undefined = item.financial_analysis
    ? {
        allocation: item.financial_analysis.allocation,
        estimatedMin: item.financial_analysis.estimated_min,
        estimatedMax: item.financial_analysis.estimated_max,
        deviationPercent: item.financial_analysis.deviation_percent,
        deviationReason: item.financial_analysis.deviation_reason,
        categoryMedian: item.financial_analysis.category_median,
      }
    : undefined;

  const similarProjects: SimilarProject[] | undefined = item.similar_projects
    ? item.similar_projects.map((sp: any) => ({
        projectId: sp.project_id,
        title: sp.title,
        similarityScore: sp.similarity_score,
        overlapReason: sp.overlap_reason,
        state: sp.state,
        constituency: sp.constituency,
      }))
    : undefined;

  const inspectionCaptures: InspectionCapture[] | undefined = item.inspection_captures
    ? item.inspection_captures.map((ic: any) => ({
        id: ic.id,
        captureDate: ic.capture_date,
        label: ic.label,
        sourceType: ic.source_type,
        imageUrl: ic.image_url,
        defectSeverity: ic.defect_severity,
        defectDescription: ic.defect_description,
      }))
    : undefined;

  const riskBreakdown: RiskBreakdown | undefined = item.risk_breakdown
    ? {
        financialScore: item.risk_breakdown.financial_score,
        nlpScore: item.risk_breakdown.nlp_score,
        imageScore: item.risk_breakdown.image_score,
        overallScore: item.risk_breakdown.overall_score,
        riskLevel: item.risk_breakdown.risk_level,
        rationale: item.risk_breakdown.rationale,
      }
    : undefined;

  const flags: AnomalyFlag[] | undefined = item.flags
    ? item.flags.map((fl: any) => ({
        id: fl.id,
        projectId: fl.project_id,
        sourceEngine: fl.source_engine,
        score: fl.score,
        reasonText: fl.reason_text,
        reviewStatus: fl.review_status,
        flaggedAt: fl.flagged_at,
        reviewerId: fl.reviewer_id,
        reviewerNotes: fl.reviewer_notes,
      }))
    : undefined;
  const rawStageIndicators = item.stage_indicator || item.stageIndicator;
  const stageIndicator: StageIndicatorEntry[] | undefined = Array.isArray(rawStageIndicators)
    ? rawStageIndicators.map((st: any) => ({
        stage: st.stage,
        flagged: Boolean(st.flagged),
        overview: st.overview,
      }))
    : undefined;
  const stageNote: string | null | undefined = item.stage_note ?? item.note ?? undefined;

  return {
    ...base,
    financialAnalysis,
    similarProjects,
    inspectionCaptures,
    riskBreakdown,
    flags,
    stageIndicator,
    stageNote,
    reviewerNotes: item.reviewer_notes,
    reviewerId: item.reviewer_id,
  };
}

// ── Real API Endpoints with Fallback ────────────────────────────────────────

/**
 * Fetch executive dashboard statistics.
 */
export async function getDashboardStats(role: UserRole = "official"): Promise<DashboardStats> {
  try {
    const res = await fetch(`${API_BASE}/dashboard/stats?role=${encodeURIComponent(role)}`, {
      headers: { "X-User-Role": role },
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      return {
        totalProjects: data.total_projects,
        totalAllocation: data.total_allocation,
        statusDistribution: toCountRecord(data.status_distribution, "status"),
        riskDistribution: toCountRecord(data.risk_distribution, "level"),
      };
    }
  } catch {
    // Backend unavailable: compute fallback stats
  }

  // Fallback computation from MOCK_PROJECTS
  const enriched = MOCK_PROJECTS.map(enrichMockProject);
  const totalProjects = enriched.length;
  const totalAllocation = enriched.reduce((acc, p) => acc + p.cost, 0);
  const statusDistribution: Record<string, number> = {};
  for (const p of enriched) {
    statusDistribution[p.status] = (statusDistribution[p.status] || 0) + 1;
  }
  const riskDistribution: Record<string, number> = { low: 0, medium: 0, high: 0 };
  for (const p of enriched) {
    const score = getProjectRiskScore(p.id);
    const lvl = scoreToRiskLevel(score);
    riskDistribution[lvl] = (riskDistribution[lvl] || 0) + 1;
  }

  return delay({
    totalProjects,
    totalAllocation,
    statusDistribution,
    riskDistribution,
  });
}

/**
 * Fetch projects filtered by state, constituency, category, status, risk level, or WORK description.
 * Returns one page of results (default 20) plus total count for pagination.
 */
export async function getProjects(
  filters: ProjectFilters = {},
  role: UserRole = "official",
  page = 1,
  pageSize = 20
): Promise<ProjectListResult> {
  const safePage = Math.max(1, page);
  const safePageSize = Math.min(2000, Math.max(1, pageSize));

  try {
    const params = new URLSearchParams();
    if (filters.state) params.set("state", filters.state);
    if (filters.constituency) params.set("constituency", filters.constituency);
    if (filters.category) params.set("category", filters.category);
    if (filters.status) params.set("status", filters.status);
    if (filters.riskLevel) params.set("risk_level", filters.riskLevel);
    if (filters.search) params.set("search", filters.search);
    params.set("role", role);
    params.set("page", String(safePage));
    params.set("page_size", String(safePageSize));

    const res = await fetch(`${API_BASE}/projects?${params.toString()}`, {
      headers: { "X-User-Role": role },
      cache: "no-store",
    });
    if (res.ok) {
      const payload = await res.json();
      const items = Array.isArray(payload) ? payload : payload.data ?? [];
      const total = Array.isArray(payload)
        ? items.length
        : Number(payload.total ?? items.length);
      return {
        data: items.map(mapProjectSummary),
        total,
        page: Number(payload.page ?? safePage),
        pageSize: Number(payload.page_size ?? safePageSize),
      };
    }
  } catch {
    // Backend unavailable: fallback
  }

  let list = MOCK_PROJECTS.map((p) => withRisk(enrichMockProject(p)));

  if (filters.state) {
    list = list.filter((p) => (p.state || "").toLowerCase() === filters.state?.toLowerCase());
  }
  if (filters.constituency) {
    list = list.filter(
      (p) => (p.constituency || "").toLowerCase() === filters.constituency?.toLowerCase()
    );
  }
  if (filters.category) {
    list = list.filter((p) => matchesCategoryFilter(p, filters.category!));
  }
  if (filters.status) {
    list = list.filter((p) => p.status.toLowerCase() === filters.status?.toLowerCase());
  }
  if (filters.riskLevel) {
    list = list.filter((p) => p.riskLevel === filters.riskLevel);
  }
  if (filters.search) {
    const q = filters.search.toLowerCase();
    list = list.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        (p.workDescription && p.workDescription.toLowerCase().includes(q)) ||
        (p.state && p.state.toLowerCase().includes(q)) ||
        (p.constituency && p.constituency.toLowerCase().includes(q)) ||
        p.district.toLowerCase().includes(q)
    );
  }

  if (role === "citizen") {
    list = list.map((p) => ({
      ...p,
      riskScore: undefined,
    }));
  }

  const total = list.length;
  const start = (safePage - 1) * safePageSize;
  const data = list.slice(start, start + safePageSize);

  return delay({
    data,
    total,
    page: safePage,
    pageSize: safePageSize,
  });
}

/**
 * Fetch detailed project record with financial analysis, similar projects, image timeline, and risk breakdown.
 */
export async function getProjectById(
  id: string,
  role: UserRole = "official"
): Promise<ProjectDetail | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(id)}?role=${encodeURIComponent(role)}`, {
      headers: { "X-User-Role": role },
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      return mapProjectDetail(data);
    }
  } catch {
    // Backend unavailable: fallback
  }

  const raw = MOCK_PROJECTS.find((item) => item.id === id);
  if (!raw) return delay(null);

  const p = enrichMockProject(raw);
  const base = withRisk(p);
  const flags = MOCK_ANOMALIES.filter((f) => f.projectId === id);

  // Dynamic benchmark financial analysis
  const benchmarksMap = stateMediansRaw as Record<string, { median: number; peerCount: number }>;
  const bench =
    (p.state && p.category && benchmarksMap[`${p.state}::${p.category}`]) ||
    (p.state && benchmarksMap[`${p.state}::Normal/Others`]) ||
    { median: 250000, peerCount: 500 };
  const catMedian = bench.median;
  const mult = p.cost / Math.max(1, catMedian);
  const isHighAnomaly = mult >= 3.0;

  const financialAnalysis: FinancialAnalysis = {
    allocation: p.cost,
    estimatedMin: Math.round(p.cost * 0.8),
    estimatedMax: Math.round(p.cost * 1.15),
    deviationPercent: Math.round(mult * 100),
    deviationReason: isHighAnomaly
      ? `Project allocation (₹${p.cost.toLocaleString("en-IN")}) is ${mult.toFixed(1)}× the ${p.state || "state"} benchmark median (₹${catMedian.toLocaleString("en-IN")}) for ${p.category || "civil"} works (peer cohort: n=${bench.peerCount.toLocaleString("en-IN")} projects). Outlier percentile: >99th.`
      : `Allocation is consistent with ${p.state || "regional"} Schedule of Rates benchmarks (median: ₹${catMedian.toLocaleString("en-IN")}).`,
    categoryMedian: catMedian,
  };

  const allFlags = [...flags];
  if (allFlags.length === 0 && isHighAnomaly) {
    allFlags.push({
      id: `dyn-flag-${p.id}`,
      projectId: p.id,
      sourceEngine: "financial",
      score: base.riskScore ?? 0.88,
      reasonText: `Project allocation (₹${p.cost.toLocaleString("en-IN")}) is ${mult.toFixed(1)}× the ${p.state} state benchmark median (₹${catMedian.toLocaleString("en-IN")}) for ${p.category} works. Flagged for financial audit.`,
      reviewStatus: "pending",
      flaggedAt: p.sanctionDate || "2024-03-04",
    });
  }

  // Fallback demo similar projects
  const similarProjects: SimilarProject[] =
    flags.some((f) => f.sourceEngine === "nlp")
      ? [
          {
            projectId: "c1e1a7cf-26ab-5167-92a1-9790ca3f069e",
            title: "Construction of Covered Common Sitting Place for Village People - Block JHAJHA",
            similarityScore: 0.96,
            overlapReason: "Identical work description and sanction parameters within same sub-district.",
            state: p.state || "Bihar",
            constituency: p.constituency || p.district,
          },
        ]
      : [];

  // Fallback demo inspection captures
  const isImageFlag = flags.some((f) => f.sourceEngine === "image");
  const inspectionCaptures: InspectionCapture[] = isImageFlag
    ? [
        {
          id: `${p.id}-cap-1`,
          captureDate: "2023-04-01",
          label: "Baseline Post-Sanction Inspection",
          sourceType: "DEMO_SYNTHETIC",
          defectSeverity: "none",
          defectDescription: "Surface intact, newly compacted asphalt, zero visible defects.",
        },
        {
          id: `${p.id}-cap-2`,
          captureDate: "2023-08-15",
          label: "Mid-Term Field Survey",
          sourceType: "DEMO_SYNTHETIC",
          defectSeverity: "minor",
          defectDescription: "Longitudinal cracking detected along shoulder edge (width 4-8mm).",
        },
        {
          id: `${p.id}-cap-3`,
          captureDate: "2023-12-10",
          label: "Audit Verification Inspection",
          sourceType: "DEMO_SYNTHETIC",
          defectSeverity: "severe",
          defectDescription: "Severe potholing and base course depression observed across 40m carriageway.",
        },
      ]
    : [
        {
          id: `${p.id}-cap-1`,
          captureDate: "2023-09-01",
          label: "Site Initial Capture",
          sourceType: p.sourceType || "DEMO_SYNTHETIC",
          defectSeverity: "none",
          defectDescription: "Site condition normal with no detected anomalies.",
        },
      ];

  const riskBreakdown: RiskBreakdown = {
    financialScore: allFlags.find((f) => f.sourceEngine === "financial")?.score ?? (base.riskScore != null && base.riskScore > 0 ? base.riskScore : 0.05),
    nlpScore: allFlags.find((f) => f.sourceEngine === "nlp")?.score ?? 0.04,
    imageScore: allFlags.find((f) => f.sourceEngine === "image")?.score ?? 0.08,
    overallScore: role === "citizen" ? undefined : base.riskScore,
    riskLevel: base.riskLevel,
    rationale:
      base.riskLevel === "high"
        ? "Statistical cost analysis detects extreme expenditure variance exceeding 3-5x regional benchmarks."
        : base.riskLevel === "medium"
        ? "Single engine flagged moderate deviation requiring verification."
        : "All parameters align with benchmark standards.",
  };

  const approvalFlagged =
    allFlags.some(
      (f) =>
        (f.sourceEngine === "financial" || f.sourceEngine === "nlp") &&
        (f.score ?? 0) >= 0.7
    ) || isHighAnomaly;

  const deliveryFlagged = allFlags.some(
    (f) => f.sourceEngine === "image" && (f.score ?? 0) >= 0.7
  );

  const stageIndicator: StageIndicatorEntry[] = [];
  if (approvalFlagged) {
    stageIndicator.push({
      stage: "approval_process",
      flagged: true,
      overview:
        "This pattern is commonly associated with irregularities in how the project was proposed or sanctioned — it does not identify any individual or agency.",
    });
  }
  if (deliveryFlagged) {
    stageIndicator.push({
      stage: "execution_delivery",
      flagged: true,
      overview:
        "This pattern is commonly associated with issues in how the work was actually carried out — it does not identify any individual or agency.",
    });
  }

  const stageNote =
    approvalFlagged && deliveryFlagged
      ? "Multiple process stages show flagged patterns; review both."
      : null;

  const detail: ProjectDetail = {
    ...base,
    financialAnalysis,
    similarProjects,
    inspectionCaptures,
    riskBreakdown,
    flags: role === "citizen" ? allFlags.map((f) => ({ ...f, reviewerId: undefined, reviewerNotes: undefined })) : allFlags,
    stageIndicator,
    stageNote,
    reviewerNotes: role === "citizen" ? undefined : "Flagged for comprehensive verification by audit panel.",
    reviewerId: role === "citizen" ? undefined : "AUDIT-OFFICIAL-402",
  };

  return delay(detail);
}

/**
 * Fetch project risk assessment and process stage indicators.
 */
export async function getProjectRisk(id: string): Promise<ProjectRiskData | null> {
  try {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(id)}/risk`, {
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      return {
        projectId: data.project_id,
        overallRiskScore: data.overall_risk_score,
        riskLevel: data.risk_level,
        riskFactors: data.risk_factors || [],
        recommendedAction: data.recommended_action,
        stageIndicator: (data.stage_indicator || []).map((s: any) => ({
          stage: s.stage,
          flagged: Boolean(s.flagged),
          overview: s.overview,
        })),
        note: data.note ?? null,
      };
    }
  } catch {
    // Backend unavailable: fallback
  }

  const detail = await getProjectById(id);
  if (!detail) return null;

  return {
    projectId: id,
    overallRiskScore: detail.riskScore ?? 0.05,
    riskLevel: detail.riskLevel,
    riskFactors: (detail.flags || []).map((f) => ({
      type: f.sourceEngine,
      score: f.score ?? 0.5,
      reason: f.reasonText,
    })),
    recommendedAction:
      detail.riskLevel === "high"
        ? "Prioritize on-site physical verification and independent financial audit before further fund disbursement."
        : "Routine monitoring and administrative review; no immediate escalation required.",
    stageIndicator: detail.stageIndicator || [],
    note: detail.stageNote ?? null,
  };
}

/**
 * Confirm or dismiss an anomaly flag.
 */
export async function updateAnomalyReviewStatus(
  id: string,
  reviewStatus: Exclude<ReviewStatus, "pending">,
  reviewerNotes?: string
): Promise<AnomalyFlag | null> {
  try {
    const res = await fetch(`${API_BASE}/anomaly-flags/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-User-Role": "official",
      },
      body: JSON.stringify({
        review_status: reviewStatus,
        reviewer_notes: reviewerNotes || `Status set to ${reviewStatus} via review interface`,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return {
        id: data.id,
        projectId: data.project_id,
        sourceEngine: data.source_engine,
        score: data.score,
        reasonText: data.reason_text,
        reviewStatus: data.review_status,
        flaggedAt: data.flagged_at,
        reviewerId: data.reviewer_id,
        reviewerNotes: data.reviewer_notes,
      };
    }
  } catch {
    // Backend unavailable: fallback
  }

  const next = MOCK_ANOMALIES.map((flag) =>
    flag.id === id
      ? {
          ...flag,
          reviewStatus,
          reviewerNotes: reviewerNotes || `Status set to ${reviewStatus}`,
          reviewerId: "OFFICIAL-UI",
        }
      : flag
  );
  replaceAnomalies(next);
  const updated = next.find((f) => f.id === id) ?? null;
  return delay(updated);
}

/**
 * Fetch Works Near Me (ONLY the 5 seeded demo projects with synthetic coordinates).
 */
export async function getWorksNearMe(role: UserRole = "official"): Promise<ProjectWithRisk[]> {
  try {
    const res = await fetch(
      `${API_BASE}/map/works-near-me?role=${encodeURIComponent(role)}`,
      {
        headers: { "X-User-Role": role },
        cache: "no-store",
      }
    );
    if (res.ok) {
      const data = await res.json();
      const items = Array.isArray(data) ? data : data.data ?? [];
      return items.map(mapProjectSummary);
    }
  } catch {
    // Backend unavailable: fallback
  }

  let list = MOCK_PROJECTS.filter((p) => DEMO_PROJECT_IDS.has(p.id)).map((p) =>
    withRisk(enrichMockProject(p))
  );
  if (role === "citizen") {
    list = list.map((p) => ({ ...p, riskScore: undefined }));
  }
  return delay(list);
}

/**
 * Fetch all geocoded projects matching filter criteria.
 * Used by the interactive Map to render pins across India and all states.
 */
export async function getGeocodedProjects(
  filters: ProjectFilters = {},
  role: UserRole = "official"
): Promise<ProjectWithRisk[]> {
  try {
    const result = await getProjects(filters, role, 1, 1500);
    const withGeo = result.data.filter(
      (p) => typeof p.lat === "number" && typeof p.lng === "number"
    );
    if (withGeo.length > 0) return withGeo;
  } catch {
    // Backend unavailable: fallback
  }

  let list = MOCK_PROJECTS.map((p) => withRisk(enrichMockProject(p))).filter(
    (p) => typeof p.lat === "number" && typeof p.lng === "number"
  );

  if (filters.state) {
    list = list.filter((p) => (p.state || "").toLowerCase() === filters.state?.toLowerCase());
  }
  if (filters.constituency) {
    list = list.filter(
      (p) => (p.constituency || "").toLowerCase() === filters.constituency?.toLowerCase()
    );
  }
  if (filters.category) {
    list = list.filter((p) => matchesCategoryFilter(p, filters.category!));
  }
  if (filters.status) {
    list = list.filter((p) => p.status.toLowerCase() === filters.status?.toLowerCase());
  }
  if (filters.riskLevel) {
    list = list.filter((p) => p.riskLevel === filters.riskLevel);
  }
  if (filters.search) {
    const q = filters.search.toLowerCase();
    list = list.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        (p.workDescription && p.workDescription.toLowerCase().includes(q)) ||
        (p.state && p.state.toLowerCase().includes(q)) ||
        (p.constituency && p.constituency.toLowerCase().includes(q)) ||
        p.district.toLowerCase().includes(q)
    );
  }

  if (role === "citizen") {
    list = list.map((p) => ({ ...p, riskScore: undefined }));
  }

  return delay(list);
}

/**
 * Fetch Administrative hierarchy (States and Constituencies).
 */
export async function getAdministrativeHierarchy(): Promise<AdministrativeHierarchy> {
  try {
    const res = await fetch(`${API_BASE}/map/administrative`, {
      cache: "no-store",
    });
    if (res.ok) {
      return normalizeHierarchy(await res.json());
    }
  } catch {
    // Backend unavailable: fallback
  }

  return delay(buildMockHierarchy());
}

// ── Legacy Helpers ─────────────────────────────────────────────────────────

export async function getAnomalyFlags(projectId?: string): Promise<AnomalyFlag[]> {
  const list = projectId
    ? MOCK_ANOMALIES.filter((f) => f.projectId === projectId)
    : [...MOCK_ANOMALIES];
  return delay(list.sort((a, b) => b.score - a.score));
}

export async function getPendingAnomalyFlags(): Promise<AnomalyFlag[]> {
  const list = MOCK_ANOMALIES.filter((f) => f.reviewStatus === "pending").sort(
    (a, b) => b.score - a.score
  );
  return delay(list);
}

export async function getProjectImages(projectId: string): Promise<ProjectImage[]> {
  const list = MOCK_IMAGES.filter((img) => img.projectId === projectId).sort((a, b) =>
    a.captureDate.localeCompare(b.captureDate)
  );
  return delay(list);
}

export async function getDistricts(): Promise<string[]> {
  const districts = Array.from(new Set(MOCK_PROJECTS.map((p) => p.district))).sort();
  return delay(districts);
}

export function getProjectTitleSync(projectId: string): string {
  return MOCK_PROJECTS.find((p) => p.id === projectId)?.title ?? "Unknown project";
}

/**
 * Query the AI Audit Assistant with natural-language questions.
 * Runs entirely offline using the local rule-based NLP engine.
 * No external API calls — eliminates all network timeout errors.
 */
export async function askAuditAssistant(
  question: string,
  role: UserRole = "official"
): Promise<AuditAssistantResponse> {
  const { runAuditEngine } = await import("./audit-engine");
  return delay(runAuditEngine(question, role));
}

