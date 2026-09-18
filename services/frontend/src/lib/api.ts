import { MOCK_ANOMALIES, MOCK_IMAGES, MOCK_PROJECTS, replaceAnomalies } from "./mock-data";
import type {
  AnomalyFlag,
  Project,
  ProjectImage,
  ProjectWithRisk,
  ReviewStatus,
  RiskLevel,
} from "./types";

/** Simulated network latency — set to 0 when wiring a real API. */
const MOCK_DELAY_MS = 40;

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
  return scores.length ? Math.max(...scores) : 0;
}

function withRisk(project: Project, flags = MOCK_ANOMALIES): ProjectWithRisk {
  const projectFlags = flags.filter((f) => f.projectId === project.id);
  const riskScore = projectFlags.length
    ? Math.max(...projectFlags.map((f) => f.score))
    : 0;
  return {
    ...project,
    riskScore,
    riskLevel: scoreToRiskLevel(riskScore),
    anomalyCount: projectFlags.length,
  };
}

export type ProjectFilters = {
  district?: string;
  type?: string;
  riskLevel?: RiskLevel | "";
};

/**
 * Fetch all projects enriched with risk metadata.
 * Swap the body for `fetch(`${API_BASE}/projects`)` later.
 */
export async function getProjects(filters: ProjectFilters = {}): Promise<ProjectWithRisk[]> {
  let list = MOCK_PROJECTS.map((p) => withRisk(p));

  if (filters.district) {
    list = list.filter((p) => p.district === filters.district);
  }
  if (filters.type) {
    list = list.filter((p) => p.type === filters.type);
  }
  if (filters.riskLevel) {
    list = list.filter((p) => p.riskLevel === filters.riskLevel);
  }

  return delay(list);
}

/** Fetch a single project by id, or null if missing. */
export async function getProjectById(id: string): Promise<ProjectWithRisk | null> {
  const project = MOCK_PROJECTS.find((p) => p.id === id);
  return delay(project ? withRisk(project) : null);
}

/** All anomaly flags, optionally scoped to one project. */
export async function getAnomalyFlags(projectId?: string): Promise<AnomalyFlag[]> {
  const list = projectId
    ? MOCK_ANOMALIES.filter((f) => f.projectId === projectId)
    : [...MOCK_ANOMALIES];
  return delay(list.sort((a, b) => b.score - a.score));
}

/** Pending flags for the review queue. */
export async function getPendingAnomalyFlags(): Promise<AnomalyFlag[]> {
  const list = MOCK_ANOMALIES.filter((f) => f.reviewStatus === "pending").sort(
    (a, b) => b.score - a.score
  );
  return delay(list);
}

/** Update review status in local mock state (no real API). */
export async function updateAnomalyReviewStatus(
  id: string,
  reviewStatus: Exclude<ReviewStatus, "pending">
): Promise<AnomalyFlag | null> {
  const next = MOCK_ANOMALIES.map((flag) =>
    flag.id === id ? { ...flag, reviewStatus } : flag
  );
  replaceAnomalies(next);
  const updated = next.find((f) => f.id === id) ?? null;
  return delay(updated);
}

/** Placeholder image captures for a project. */
export async function getProjectImages(projectId: string): Promise<ProjectImage[]> {
  const list = MOCK_IMAGES.filter((img) => img.projectId === projectId).sort((a, b) =>
    a.captureDate.localeCompare(b.captureDate)
  );
  return delay(list);
}

/** Distinct districts for filter dropdowns. */
export async function getDistricts(): Promise<string[]> {
  const districts = Array.from(new Set(MOCK_PROJECTS.map((p) => p.district))).sort();
  return delay(districts);
}

/** Resolve project title quickly for list UIs. */
export function getProjectTitleSync(projectId: string): string {
  return MOCK_PROJECTS.find((p) => p.id === projectId)?.title ?? "Unknown project";
}
