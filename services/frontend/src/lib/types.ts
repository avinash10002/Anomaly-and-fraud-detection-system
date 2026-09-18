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

export interface Project {
  id: string;
  title: string;
  type: ProjectType;
  sanctionDate: string;
  completionDate: string | null;
  cost: number;
  lat: number;
  lng: number;
  district: string;
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
}

export interface ProjectImage {
  id: string;
  projectId: string;
  captureDate: string;
  label: string;
  source: "streetview" | "mapillary" | "upload";
}

export interface ProjectWithRisk extends Project {
  riskScore: number;
  riskLevel: RiskLevel;
  anomalyCount: number;
}
