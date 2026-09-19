export type ProjectType = "road" | "building" | "park" | "other";
export type ProjectStatus =
  | "planned"
  | "ongoing"
  | "completed"
  | "stalled"
  | "cancelled";
export type SourceEngine = "financial" | "image" | "nlp";
export type ReviewStatus = "pending" | "confirmed" | "dismissed";
export type RiskLevel = "low" | "medium" | "high";
export type UserRole = "citizen" | "official";

export interface Project {
  id: string;
  title: string;
  type: ProjectType;
  sanctionDate: string;
  completionDate: string | null;
  cost: number;
  lat?: number;
  lng?: number;
  district: string;
  state?: string;
  constituency?: string;
  workDescription?: string;
  category?: string;
  sourceType?: "DEMO_SYNTHETIC" | "MPLADS_HISTORIC";
  contractorName: string;
  mpName: string;
  status: ProjectStatus;
}

export interface AnomalyFlag {
  id: string;
  projectId: string;
  sourceEngine: SourceEngine;
  score: number;
  reasonText: string;
  reviewStatus: ReviewStatus;
  /** ISO date when the flag was raised — used on the detail timeline */
  flaggedAt: string;
  reviewerId?: string;
  reviewerNotes?: string;
}

export interface ProjectImage {
  id: string;
  projectId: string;
  captureDate: string;
  label: string;
  source: "streetview" | "mapillary" | "upload";
}

export interface ProjectWithRisk extends Project {
  riskScore?: number; // Optional because citizen role redacts numeric score
  riskLevel: RiskLevel;
  anomalyCount: number;
}

export interface FinancialAnalysis {
  allocation: number;
  estimatedMin: number;
  estimatedMax: number;
  deviationPercent: number;
  deviationReason: string;
  categoryMedian: number;
}

export interface SimilarProject {
  projectId: string;
  title: string;
  similarityScore: number;
  overlapReason: string;
  state?: string;
  constituency?: string;
}

export interface InspectionCapture {
  id: string;
  captureDate: string;
  label: string;
  sourceType: "DEMO_SYNTHETIC" | "MPLADS_HISTORIC";
  imageUrl?: string;
  defectSeverity: "none" | "minor" | "moderate" | "severe";
  defectDescription: string;
}

export interface RiskBreakdown {
  financialScore: number;
  nlpScore: number;
  imageScore: number;
  overallScore?: number;
  riskLevel: RiskLevel;
  rationale: string;
}

export interface StageIndicatorEntry {
  stage: "approval_process" | "execution_delivery" | string;
  flagged: boolean;
  overview: string;
}

export interface ProjectRiskData {
  projectId: string;
  overallRiskScore: number;
  riskLevel: RiskLevel;
  riskFactors: Array<{
    type: string;
    score: number;
    reason: string;
  }>;
  recommendedAction: string;
  stageIndicator: StageIndicatorEntry[];
  note?: string | null;
}

export interface ProjectDetail extends ProjectWithRisk {
  financialAnalysis?: FinancialAnalysis;
  similarProjects?: SimilarProject[];
  inspectionCaptures?: InspectionCapture[];
  riskBreakdown?: RiskBreakdown;
  flags?: AnomalyFlag[];
  stageIndicator?: StageIndicatorEntry[];
  stageNote?: string | null;
  reviewerNotes?: string;
  reviewerId?: string;
}

export interface DashboardStats {
  totalProjects: number;
  totalAllocation: number;
  statusDistribution: Record<string, number>;
  riskDistribution: Record<string, number>;
}

export interface ProjectFilters {
  state?: string;
  constituency?: string;
  category?: string;
  status?: string;
  riskLevel?: string;
  search?: string;
}

export interface ProjectListResult {
  data: ProjectWithRisk[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AdministrativeHierarchy {
  states: string[];
  constituenciesByState: Record<string, string[]>;
}

export interface ProjectCitation {
  projectId: string;
  title: string;
  state?: string;
  constituency?: string;
  allocation?: number;
  category?: string;
  flags: string[];
}

export interface AuditAssistantResponse {
  question: string;
  answer: string;
  citations: ProjectCitation[];
  intent: string;
  recordsFound: number;
  safeAuditLanguage: boolean;
  disclaimer: string;
}

