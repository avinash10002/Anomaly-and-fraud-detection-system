/**
 * audit-engine.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Fully offline, rule-based NLP audit assistant for MPLADS data.
 * No external API calls — all analysis runs on local project + anomaly records.
 *
 * Architecture:
 *  1. Intent Detection   – keyword/pattern matching → Intent enum
 *  2. Entity Extraction  – state, constituency, category, status, contractor,
 *                          MP name, amount range, date range from the question
 *  3. Data Filtering     – apply extracted entities as typed predicates
 *  4. Insight Generation – rule engine produces structured audit findings
 *  5. Response Builder   – formats answer, citations, disclaimer
 */

import { MOCK_ANOMALIES, MOCK_PROJECTS } from "./mock-data";
import type { AnomalyFlag, Project, UserRole } from "./types";
import type { AuditAssistantResponse, ProjectCitation } from "./types";

// ─── Types ────────────────────────────────────────────────────────────────────

type Intent =
  | "EXPENSIVE_PROJECTS"
  | "HIGH_RISK_PROJECTS"
  | "PENDING_PROJECTS"
  | "STALLED_PROJECTS"
  | "FINANCIAL_ANOMALIES"
  | "NLP_ANOMALIES"
  | "IMAGE_ANOMALIES"
  | "CONTRACTOR_SEARCH"
  | "MP_SEARCH"
  | "STATE_SUMMARY"
  | "CONSTITUENCY_SUMMARY"
  | "CATEGORY_SUMMARY"
  | "DUPLICATE_PROJECTS"
  | "COMPLETED_PROJECTS"
  | "CANCELLED_PROJECTS"
  | "TOTAL_ALLOCATION"
  | "ANOMALY_SUMMARY"
  | "PROJECT_SEARCH"
  | "GENERAL";

interface Entities {
  state?: string;
  constituency?: string;
  category?: string;
  status?: string;
  contractorName?: string;
  mpName?: string;
  minCost?: number;
  maxCost?: number;
  keyword?: string;
}

interface EnrichedProject extends Project {
  anomalyFlags: AnomalyFlag[];
  maxRiskScore: number;
  riskLevel: "low" | "medium" | "high";
}

// ─── Constants ────────────────────────────────────────────────────────────────

const INDIAN_STATES = [
  "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
  "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
  "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
  "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
  "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
  "andaman and nicobar", "chandigarh", "dadra", "daman", "delhi", "jammu",
  "kashmir", "ladakh", "lakshadweep", "puducherry",
];

const CATEGORIES = [
  "roads and bridges",
  "community infrastructure",
  "sports / recreation",
  "education",
  "health",
  "water and sanitation",
  "other works",
];

const STOP_WORDS = new Set([
  "a", "an", "the", "in", "on", "of", "for", "to", "is", "are", "was",
  "were", "and", "or", "but", "with", "that", "this", "which", "have",
  "has", "had", "do", "does", "did", "show", "me", "give", "list", "find",
  "what", "how", "why", "who", "where", "when", "any", "all", "most",
  "many", "some", "more", "very", "too", "just", "also", "there", "their",
  "they", "from", "by", "at", "as", "be", "been", "being", "will", "would",
  "should", "could", "may", "might", "can", "shall",
]);

// ─── Utility helpers ──────────────────────────────────────────────────────────

function normalise(s: string): string {
  return s.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
}

function formatINR(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// ─── Enrichment ───────────────────────────────────────────────────────────────

function enrichAll(): EnrichedProject[] {
  return MOCK_PROJECTS.map((p) => {
    const flags = MOCK_ANOMALIES.filter((f) => f.projectId === p.id);
    const scores = flags.map((f) => f.score);
    const maxRiskScore = scores.length ? Math.max(...scores) : 0;
    const riskLevel: "low" | "medium" | "high" =
      maxRiskScore > 0.7 ? "high" : maxRiskScore >= 0.3 ? "medium" : "low";
    return { ...p, anomalyFlags: flags, maxRiskScore, riskLevel };
  });
}

// ─── Intent Detection ─────────────────────────────────────────────────────────

const INTENT_PATTERNS: Array<{ intents: Intent[]; patterns: RegExp[] }> = [
  {
    intents: ["EXPENSIVE_PROJECTS"],
    patterns: [
      /expensive|costly|high.?cost|overpriced|overvalued|highest.?(cost|allocation|budget|amount)|most.?expensive|top.?cost|largest.?(allocation|fund)|biggest.?(project|amount)/i,
    ],
  },
  {
    intents: ["HIGH_RISK_PROJECTS"],
    patterns: [
      /high.?risk|flagged|anomaly|anomalies|suspicious|fraud|irregularit|risk.?score|red.?flag/i,
    ],
  },
  {
    intents: ["FINANCIAL_ANOMALIES"],
    patterns: [
      /financial.?(anomaly|flag|issue|irregularity)|overbill|billing|duplicate.?invoice|cost.?overshoot|budget.?deviation|financial.?fraud/i,
    ],
  },
  {
    intents: ["NLP_ANOMALIES"],
    patterns: [
      /nlp|text|description|similar.?text|duplicate.?description|copy.?paste|boilerplate|identical.?scope|repeated.?work/i,
    ],
  },
  {
    intents: ["IMAGE_ANOMALIES"],
    patterns: [
      /image|photo|satellite|pothole|crack|defect|degradation|visual|mapillary|streetview|street.?view|physical.?condition/i,
    ],
  },
  {
    intents: ["PENDING_PROJECTS"],
    patterns: [/pending|not.?started|upcoming|new.?project|unstarted/i],
  },
  {
    intents: ["STALLED_PROJECTS"],
    patterns: [/stalled|stuck|halted|stopped|delayed|no.?progress|abandon/i],
  },
  {
    intents: ["COMPLETED_PROJECTS"],
    patterns: [/completed|finished|done|handover|delivered/i],
  },
  {
    intents: ["CANCELLED_PROJECTS"],
    patterns: [/cancelled|canceled|dropped|terminated|scrapped/i],
  },
  {
    intents: ["CONTRACTOR_SEARCH"],
    patterns: [/contractor|vendor|supplier|firm|company|builder|awarded.?to/i],
  },
  {
    intents: ["MP_SEARCH"],
    patterns: [/mp|member.?of.?parliament|minister|mla|politician|elected|representative/i],
  },
  {
    intents: ["DUPLICATE_PROJECTS"],
    patterns: [/duplicate|double|repeated|overlap|same.?project|twin.?project/i],
  },
  {
    intents: ["TOTAL_ALLOCATION"],
    patterns: [/total.?(allocation|fund|budget|spend|spending|amount)|how.?much.?(spend|allocat|fund)|sum.?of/i],
  },
  {
    intents: ["ANOMALY_SUMMARY"],
    patterns: [/summary|overview|report|audit.?report|all.?anomal|anomaly.?overview|how.?many.?(flag|anomal)/i],
  },
  {
    intents: ["STATE_SUMMARY"],
    patterns: [/state.?(summary|breakdown|report|wise)|by.?state|which.?state|most.?(project|fund).?in/i],
  },
  {
    intents: ["CONSTITUENCY_SUMMARY"],
    patterns: [/constituency|most.?pending|which.?constituency|constituency.?wise|mp.?constituency/i],
  },
  {
    intents: ["CATEGORY_SUMMARY"],
    patterns: [/category|type.?of.?project|sector|road.?project|building.?project|education.?project|health.?project/i],
  },
];

function detectIntent(q: string): Intent {
  for (const { intents, patterns } of INTENT_PATTERNS) {
    for (const pat of patterns) {
      if (pat.test(q)) return intents[0];
    }
  }
  return "PROJECT_SEARCH";
}

// ─── Entity Extraction ────────────────────────────────────────────────────────

function extractEntities(q: string): Entities {
  const norm = normalise(q);
  const entities: Entities = {};

  // State
  for (const state of INDIAN_STATES) {
    if (norm.includes(state)) {
      entities.state = state
        .split(" ")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
      break;
    }
  }

  // Category
  for (const cat of CATEGORIES) {
    if (norm.includes(cat) || (cat === "roads and bridges" && /\broad(s)?\b/.test(norm))) {
      entities.category = cat;
      break;
    }
  }
  if (!entities.category && /\broads?\b/.test(norm)) entities.category = "roads and bridges";
  if (!entities.category && /\bhealth\b/.test(norm)) entities.category = "health";
  if (!entities.category && /\beducation\b/.test(norm)) entities.category = "education";
  if (!entities.category && /\bwater\b/.test(norm)) entities.category = "water and sanitation";
  if (!entities.category && /\bsport|park|recreation\b/.test(norm)) entities.category = "sports / recreation";

  // Status
  if (/\bpending\b/.test(norm)) entities.status = "planned";
  if (/\bstalled?\b/.test(norm)) entities.status = "stalled";
  if (/\bcompleted?\b/.test(norm)) entities.status = "completed";
  if (/\bcancell?ed?\b/.test(norm)) entities.status = "cancelled";
  if (/\bongoing\b/.test(norm)) entities.status = "ongoing";

  // Amount range – e.g. "above 5 crore", "more than 10 cr", "over 1 crore"
  const aboveMatch = norm.match(/(?:above|more than|over|greater than|exceeding)\s+([\d.]+)\s*(crore|cr|lakh|l)/i);
  if (aboveMatch) {
    const val = parseFloat(aboveMatch[1]);
    const unit = aboveMatch[2].toLowerCase();
    entities.minCost = unit.startsWith("c") ? val * 1e7 : val * 1e5;
  }
  const belowMatch = norm.match(/(?:below|less than|under|within)\s+([\d.]+)\s*(crore|cr|lakh|l)/i);
  if (belowMatch) {
    const val = parseFloat(belowMatch[1]);
    const unit = belowMatch[2].toLowerCase();
    entities.maxCost = unit.startsWith("c") ? val * 1e7 : val * 1e5;
  }

  // Keyword — leftover meaningful words
  const words = norm.split(" ").filter((w) => w.length > 3 && !STOP_WORDS.has(w));
  if (words.length) entities.keyword = words.join(" ");

  return entities;
}

// ─── Data Filtering ───────────────────────────────────────────────────────────

function applyFilters(projects: EnrichedProject[], entities: Entities): EnrichedProject[] {
  return projects.filter((p) => {
    if (entities.state && !(p.state || "").toLowerCase().includes(entities.state.toLowerCase())) return false;
    if (entities.constituency && !(p.constituency || "").toLowerCase().includes(entities.constituency.toLowerCase())) return false;
    if (entities.category && !(p.category || "").toLowerCase().includes(entities.category.toLowerCase())) return false;
    if (entities.status && p.status !== entities.status) return false;
    if (entities.contractorName && !(p.contractorName || "").toLowerCase().includes(entities.contractorName.toLowerCase())) return false;
    if (entities.mpName && !(p.mpName || "").toLowerCase().includes(entities.mpName.toLowerCase())) return false;
    if (entities.minCost !== undefined && p.cost < entities.minCost) return false;
    if (entities.maxCost !== undefined && p.cost > entities.maxCost) return false;
    return true;
  });
}

// ─── Rule Engine (per-intent insight generators) ──────────────────────────────

interface EngineResult {
  answer: string;
  citations: ProjectCitation[];
  recordsFound: number;
}

function ruleExpensiveProjects(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, entities);
  if (!filtered.length) return noData(entities);

  const sorted = [...filtered].sort((a, b) => b.cost - a.cost).slice(0, 10);
  const costValues = filtered.map((p) => p.cost);
  const med = median(costValues);
  const outliers = sorted.filter((p) => p.cost > med * 2);

  const stateCtx = entities.state ? ` in ${entities.state}` : "";
  const catCtx = entities.category ? ` (${entities.category})` : "";

  let answer = `**Highest-allocation projects${stateCtx}${catCtx}** — Top ${sorted.length} of ${filtered.length} records:\n\n`;
  sorted.forEach((p, i) => {
    const ratio = med > 0 ? (p.cost / med).toFixed(1) : "N/A";
    const flagNote = p.anomalyFlags.length ? ` ⚠️ ${p.anomalyFlags.length} anomaly flag(s)` : "";
    answer += `${i + 1}. **${p.title}** — ${formatINR(p.cost)} (${ratio}× state median)${flagNote}\n   ${p.constituency || p.district}, ${p.state || "—"} · ${p.category || "—"}\n\n`;
  });

  if (outliers.length) {
    answer += `\n📊 **Statistical Outliers (>2× state median of ${formatINR(med)}):** ${outliers.length} project(s) identified for audit review.`;
  }

  return { answer, citations: sorted.map(toCitation), recordsFound: filtered.length };
}

function ruleHighRiskProjects(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, entities).filter((p) => p.maxRiskScore > 0);
  if (!filtered.length) return noData(entities);

  const sorted = [...filtered].sort((a, b) => b.maxRiskScore - a.maxRiskScore).slice(0, 10);
  const stateCtx = entities.state ? ` in ${entities.state}` : "";

  let answer = `**High-risk projects${stateCtx}** — ${filtered.length} total flagged records. Top ${sorted.length} by risk score:\n\n`;
  sorted.forEach((p, i) => {
    const scoreLabel = (p.maxRiskScore * 100).toFixed(0);
    const engines = [...new Set(p.anomalyFlags.map((f) => f.sourceEngine))].join(", ");
    answer += `${i + 1}. **${p.title}** — Risk: ${scoreLabel}% · Engines: ${engines}\n   ${formatINR(p.cost)} · ${p.constituency || p.district}, ${p.state || "—"}\n   _Top flag: ${p.anomalyFlags.sort((a, b) => b.score - a.score)[0]?.reasonText}_\n\n`;
  });

  return { answer, citations: sorted.map(toCitation), recordsFound: filtered.length };
}

function ruleAnomalyByEngine(
  projects: EnrichedProject[],
  entities: Entities,
  engine: "financial" | "nlp" | "image"
): EngineResult {
  const filtered = applyFilters(projects, entities).filter((p) =>
    p.anomalyFlags.some((f) => f.sourceEngine === engine)
  );
  if (!filtered.length) return noData(entities);

  const sorted = [...filtered]
    .sort((a, b) => {
      const aScore = Math.max(...a.anomalyFlags.filter((f) => f.sourceEngine === engine).map((f) => f.score));
      const bScore = Math.max(...b.anomalyFlags.filter((f) => f.sourceEngine === engine).map((f) => f.score));
      return bScore - aScore;
    })
    .slice(0, 10);

  const engineLabels: Record<string, string> = {
    financial: "Financial Irregularity",
    nlp: "NLP / Text Similarity",
    image: "Image / Visual Degradation",
  };

  const stateCtx = entities.state ? ` in ${entities.state}` : "";
  let answer = `**${engineLabels[engine]} anomalies${stateCtx}** — ${filtered.length} project(s) flagged:\n\n`;
  sorted.forEach((p, i) => {
    const relevantFlags = p.anomalyFlags
      .filter((f) => f.sourceEngine === engine)
      .sort((a, b) => b.score - a.score);
    const topFlag = relevantFlags[0];
    answer += `${i + 1}. **${p.title}** — ${formatINR(p.cost)}\n   ${p.constituency || p.district}, ${p.state || "—"}\n   🔍 _${topFlag?.reasonText}_\n\n`;
  });

  return { answer, citations: sorted.map(toCitation), recordsFound: filtered.length };
}

function ruleStatusProjects(
  projects: EnrichedProject[],
  entities: Entities,
  status: "planned" | "stalled" | "completed" | "cancelled" | "ongoing"
): EngineResult {
  const filtered = applyFilters(projects, { ...entities, status });
  if (!filtered.length) return noData({ ...entities, status });

  const byConstituency: Record<string, EnrichedProject[]> = {};
  for (const p of filtered) {
    const key = `${p.constituency || p.district}, ${p.state || "—"}`;
    if (!byConstituency[key]) byConstituency[key] = [];
    byConstituency[key].push(p);
  }

  const sorted = Object.entries(byConstituency)
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 8);

  const statusLabels: Record<string, string> = {
    planned: "Pending / Planned",
    stalled: "Stalled",
    completed: "Completed",
    cancelled: "Cancelled",
    ongoing: "Ongoing",
  };

  const stateCtx = entities.state ? ` in ${entities.state}` : "";
  let answer = `**${statusLabels[status]} projects${stateCtx}** — ${filtered.length} total records.\n\n`;

  if (status === "stalled" || status === "planned") {
    answer += `**Constituencies with the most ${statusLabels[status].toLowerCase()} projects:**\n\n`;
    sorted.forEach(([constituency, projs], i) => {
      const totalFunds = projs.reduce((s, p) => s + p.cost, 0);
      answer += `${i + 1}. **${constituency}** — ${projs.length} project(s), ${formatINR(totalFunds)} allocated\n`;
    });
    answer += `\n_Total funds held in ${statusLabels[status].toLowerCase()} projects: ${formatINR(filtered.reduce((s, p) => s + p.cost, 0))}_`;
  } else {
    answer += `**Sample records:**\n\n`;
    filtered.slice(0, 8).forEach((p, i) => {
      answer += `${i + 1}. **${p.title}** — ${formatINR(p.cost)} · ${p.constituency || p.district}, ${p.state || "—"}\n`;
    });
  }

  return {
    answer,
    citations: filtered.slice(0, 10).map(toCitation),
    recordsFound: filtered.length,
  };
}

function ruleContractorSearch(projects: EnrichedProject[], entities: Entities): EngineResult {
  const keyword = entities.keyword || "";
  const filtered = projects.filter((p) =>
    keyword
      ? (p.contractorName || "").toLowerCase().includes(keyword) ||
        (p.title || "").toLowerCase().includes(keyword)
      : true
  );

  // Count per contractor
  const byContractor: Record<string, { count: number; totalCost: number; flagCount: number }> = {};
  for (const p of filtered) {
    const c = p.contractorName || "Unknown";
    if (!byContractor[c]) byContractor[c] = { count: 0, totalCost: 0, flagCount: 0 };
    byContractor[c].count++;
    byContractor[c].totalCost += p.cost;
    byContractor[c].flagCount += p.anomalyFlags.length;
  }

  const sorted = Object.entries(byContractor)
    .sort((a, b) => b[1].flagCount - a[1].flagCount || b[1].count - a[1].count)
    .slice(0, 10);

  let answer = `**Contractor analysis** — ${Object.keys(byContractor).length} unique contractors across ${filtered.length} project(s).\n\n`;
  answer += `**Top contractors by anomaly flag count:**\n\n`;
  sorted.forEach(([name, stats], i) => {
    const flagNote = stats.flagCount > 0 ? ` ⚠️ ${stats.flagCount} flag(s)` : " ✅ No flags";
    answer += `${i + 1}. **${name}** — ${stats.count} project(s), ${formatINR(stats.totalCost)}${flagNote}\n`;
  });

  const topFlagged = filtered.filter((p) => p.anomalyFlags.length > 0).slice(0, 8);
  return { answer, citations: topFlagged.map(toCitation), recordsFound: filtered.length };
}

function ruleMpSearch(projects: EnrichedProject[], entities: Entities): EngineResult {
  const keyword = entities.keyword || "";
  const filtered = applyFilters(projects, entities).filter((p) =>
    keyword ? (p.mpName || "").toLowerCase().includes(keyword) : true
  );

  const byMp: Record<string, { count: number; totalCost: number; flagCount: number }> = {};
  for (const p of filtered) {
    const mp = p.mpName || "Unknown";
    if (!byMp[mp]) byMp[mp] = { count: 0, totalCost: 0, flagCount: 0 };
    byMp[mp].count++;
    byMp[mp].totalCost += p.cost;
    byMp[mp].flagCount += p.anomalyFlags.length;
  }

  const sorted = Object.entries(byMp)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 10);

  let answer = `**MP-wise project analysis** — ${Object.keys(byMp).length} MP(s) across ${filtered.length} project(s).\n\n`;
  sorted.forEach(([mp, stats], i) => {
    const flagNote = stats.flagCount > 0 ? ` ⚠️ ${stats.flagCount} flag(s)` : "";
    answer += `${i + 1}. **${mp}** — ${stats.count} project(s), ${formatINR(stats.totalCost)}${flagNote}\n`;
  });

  return { answer, citations: filtered.slice(0, 8).map(toCitation), recordsFound: filtered.length };
}

function ruleStateSummary(projects: EnrichedProject[], _entities: Entities): EngineResult {
  const byState: Record<string, { count: number; totalCost: number; flagCount: number; stalledCount: number }> = {};
  for (const p of projects) {
    const state = p.state || "Unknown";
    if (!byState[state]) byState[state] = { count: 0, totalCost: 0, flagCount: 0, stalledCount: 0 };
    byState[state].count++;
    byState[state].totalCost += p.cost;
    byState[state].flagCount += p.anomalyFlags.length;
    if (p.status === "stalled") byState[state].stalledCount++;
  }

  const sorted = Object.entries(byState)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 15);

  let answer = `**State-wise MPLADS project summary** — ${Object.keys(byState).length} states, ${projects.length} total projects:\n\n`;
  sorted.forEach(([state, stats], i) => {
    const flagNote = stats.flagCount > 0 ? ` · ⚠️ ${stats.flagCount} flags` : "";
    const stalledNote = stats.stalledCount > 0 ? ` · 🔴 ${stats.stalledCount} stalled` : "";
    answer += `${i + 1}. **${state}** — ${stats.count} project(s), ${formatINR(stats.totalCost)}${flagNote}${stalledNote}\n`;
  });

  return { answer, citations: [], recordsFound: projects.length };
}

function ruleConstituencySummary(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, entities);
  const byConst: Record<string, { count: number; pending: number; totalCost: number }> = {};
  for (const p of filtered) {
    const key = `${p.constituency || p.district} (${p.state || "—"})`;
    if (!byConst[key]) byConst[key] = { count: 0, pending: 0, totalCost: 0 };
    byConst[key].count++;
    if (p.status === "planned" || p.status === "stalled") byConst[key].pending++;
    byConst[key].totalCost += p.cost;
  }

  const sorted = Object.entries(byConst)
    .sort((a, b) => b[1].pending - a[1].pending)
    .slice(0, 12);

  let answer = `**Constituency-wise project summary** (ranked by pending/stalled count):\n\n`;
  sorted.forEach(([name, stats], i) => {
    answer += `${i + 1}. **${name}** — ${stats.count} project(s) · ${stats.pending} pending/stalled · ${formatINR(stats.totalCost)}\n`;
  });

  return { answer, citations: [], recordsFound: filtered.length };
}

function ruleCategorySummary(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, { ...entities, category: undefined });
  const byCat: Record<string, { count: number; totalCost: number; flagCount: number }> = {};
  for (const p of filtered) {
    const cat = p.category || "Other Works";
    if (!byCat[cat]) byCat[cat] = { count: 0, totalCost: 0, flagCount: 0 };
    byCat[cat].count++;
    byCat[cat].totalCost += p.cost;
    byCat[cat].flagCount += p.anomalyFlags.length;
  }

  const sorted = Object.entries(byCat).sort((a, b) => b[1].count - a[1].count);
  const stateCtx = entities.state ? ` in ${entities.state}` : "";

  let answer = `**Category-wise project breakdown${stateCtx}** — ${filtered.length} total projects:\n\n`;
  sorted.forEach(([cat, stats], i) => {
    const flagNote = stats.flagCount > 0 ? ` · ⚠️ ${stats.flagCount} anomaly flag(s)` : "";
    answer += `${i + 1}. **${cat}** — ${stats.count} project(s), ${formatINR(stats.totalCost)}${flagNote}\n`;
  });

  return { answer, citations: [], recordsFound: filtered.length };
}

function ruleTotalAllocation(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, entities);
  const total = filtered.reduce((s, p) => s + p.cost, 0);
  const med = median(filtered.map((p) => p.cost));
  const flagged = filtered.filter((p) => p.anomalyFlags.length > 0);

  const stateCtx = entities.state ? ` in ${entities.state}` : "";
  const catCtx = entities.category ? ` for ${entities.category}` : "";

  const answer =
    `**Total MPLADS allocation${stateCtx}${catCtx}:**\n\n` +
    `💰 **${formatINR(total)}** across **${filtered.length}** project(s)\n` +
    `📊 Median per project: **${formatINR(med)}**\n` +
    `⚠️ Projects with anomaly flags: **${flagged.length}** (${((flagged.length / filtered.length) * 100).toFixed(1)}%)\n` +
    `🔴 Funds in flagged projects: **${formatINR(flagged.reduce((s, p) => s + p.cost, 0))}**`;

  return { answer, citations: [], recordsFound: filtered.length };
}

function ruleAnomalySummary(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, entities);
  const allFlags = filtered.flatMap((p) => p.anomalyFlags);
  const pending = allFlags.filter((f) => f.reviewStatus === "pending");
  const confirmed = allFlags.filter((f) => f.reviewStatus === "confirmed");
  const dismissed = allFlags.filter((f) => f.reviewStatus === "dismissed");
  const byEngine = {
    financial: allFlags.filter((f) => f.sourceEngine === "financial").length,
    nlp: allFlags.filter((f) => f.sourceEngine === "nlp").length,
    image: allFlags.filter((f) => f.sourceEngine === "image").length,
  };

  const stateCtx = entities.state ? ` in ${entities.state}` : "";
  const answer =
    `**MPLADS Anomaly Audit Summary${stateCtx}**\n\n` +
    `📋 Total anomaly flags: **${allFlags.length}**\n` +
    `   • 🟡 Pending review: **${pending.length}**\n` +
    `   • 🔴 Confirmed: **${confirmed.length}**\n` +
    `   • ✅ Dismissed: **${dismissed.length}**\n\n` +
    `**By Detection Engine:**\n` +
    `   • 💰 Financial irregularity: **${byEngine.financial}** flags\n` +
    `   • 📝 NLP / text similarity: **${byEngine.nlp}** flags\n` +
    `   • 📷 Image / visual: **${byEngine.image}** flags\n\n` +
    `Projects flagged: **${filtered.filter((p) => p.anomalyFlags.length > 0).length}** of ${filtered.length} total`;

  const topFlagged = filtered
    .filter((p) => p.anomalyFlags.length > 0)
    .sort((a, b) => b.maxRiskScore - a.maxRiskScore)
    .slice(0, 8);

  return { answer, citations: topFlagged.map(toCitation), recordsFound: filtered.length };
}

function ruleDuplicateProjects(projects: EnrichedProject[], entities: Entities): EngineResult {
  const filtered = applyFilters(projects, entities).filter((p) =>
    p.anomalyFlags.some(
      (f) =>
        f.sourceEngine === "nlp" &&
        (f.reasonText.toLowerCase().includes("similar") ||
          f.reasonText.toLowerCase().includes("duplicate") ||
          f.reasonText.toLowerCase().includes("identical") ||
          f.reasonText.toLowerCase().includes("cosine"))
    )
  );

  if (!filtered.length) return noData(entities);

  const stateCtx = entities.state ? ` in ${entities.state}` : "";
  let answer = `**Duplicate / similar-description projects${stateCtx}** — ${filtered.length} flagged by NLP engine:\n\n`;
  filtered.slice(0, 10).forEach((p, i) => {
    const nlpFlags = p.anomalyFlags.filter((f) => f.sourceEngine === "nlp");
    answer += `${i + 1}. **${p.title}** — ${formatINR(p.cost)}\n   ${p.constituency || p.district}, ${p.state || "—"}\n   _${nlpFlags[0]?.reasonText}_\n\n`;
  });

  return { answer, citations: filtered.slice(0, 10).map(toCitation), recordsFound: filtered.length };
}

function ruleProjectSearch(projects: EnrichedProject[], entities: Entities): EngineResult {
  const keyword = (entities.keyword || "").toLowerCase();
  const filtered = applyFilters(
    keyword
      ? projects.filter(
          (p) =>
            p.title.toLowerCase().includes(keyword) ||
            (p.workDescription || "").toLowerCase().includes(keyword) ||
            (p.district || "").toLowerCase().includes(keyword) ||
            (p.mpName || "").toLowerCase().includes(keyword) ||
            (p.contractorName || "").toLowerCase().includes(keyword)
        )
      : projects,
    entities
  );

  if (!filtered.length) return noData(entities);

  const sorted = [...filtered].sort((a, b) => b.maxRiskScore - a.maxRiskScore).slice(0, 10);
  const stateCtx = entities.state ? ` in ${entities.state}` : "";

  let answer = `**Project search results${stateCtx}** — ${filtered.length} record(s) matched.\n\n`;
  sorted.forEach((p, i) => {
    const flagNote = p.anomalyFlags.length ? ` ⚠️ ${p.anomalyFlags.length} flag(s)` : "";
    answer += `${i + 1}. **${p.title}** — ${formatINR(p.cost)} · ${p.status}${flagNote}\n   ${p.constituency || p.district}, ${p.state || "—"} · ${p.category || "—"}\n`;
  });

  return { answer, citations: sorted.map(toCitation), recordsFound: filtered.length };
}

// ─── Citation Builder ─────────────────────────────────────────────────────────

function toCitation(p: EnrichedProject): ProjectCitation {
  return {
    projectId: p.id,
    title: p.title,
    state: p.state,
    constituency: p.constituency || p.district,
    allocation: p.cost,
    category: p.category,
    flags: p.anomalyFlags
      .sort((a, b) => b.score - a.score)
      .slice(0, 2)
      .map((f) => f.reasonText),
  };
}

function noData(entities: Entities): EngineResult {
  const ctx = [entities.state, entities.category, entities.status].filter(Boolean).join(", ");
  return {
    answer: `No records matched your query${ctx ? ` for: ${ctx}` : ""}. Try broadening your search criteria.`,
    citations: [],
    recordsFound: 0,
  };
}

// ─── Main Entry Point ─────────────────────────────────────────────────────────

export function runAuditEngine(
  question: string,
  _role: UserRole = "official"
): AuditAssistantResponse {
  const projects = enrichAll();
  const intent = detectIntent(question);
  const entities = extractEntities(question);

  let result: EngineResult;

  switch (intent) {
    case "EXPENSIVE_PROJECTS":
      result = ruleExpensiveProjects(projects, entities);
      break;
    case "HIGH_RISK_PROJECTS":
      result = ruleHighRiskProjects(projects, entities);
      break;
    case "FINANCIAL_ANOMALIES":
      result = ruleAnomalyByEngine(projects, entities, "financial");
      break;
    case "NLP_ANOMALIES":
      result = ruleAnomalyByEngine(projects, entities, "nlp");
      break;
    case "IMAGE_ANOMALIES":
      result = ruleAnomalyByEngine(projects, entities, "image");
      break;
    case "PENDING_PROJECTS":
      result = ruleStatusProjects(projects, entities, "planned");
      break;
    case "STALLED_PROJECTS":
      result = ruleStatusProjects(projects, entities, "stalled");
      break;
    case "COMPLETED_PROJECTS":
      result = ruleStatusProjects(projects, entities, "completed");
      break;
    case "CANCELLED_PROJECTS":
      result = ruleStatusProjects(projects, entities, "cancelled");
      break;
    case "CONTRACTOR_SEARCH":
      result = ruleContractorSearch(projects, entities);
      break;
    case "MP_SEARCH":
      result = ruleMpSearch(projects, entities);
      break;
    case "STATE_SUMMARY":
      result = ruleStateSummary(projects, entities);
      break;
    case "CONSTITUENCY_SUMMARY":
      result = ruleConstituencySummary(projects, entities);
      break;
    case "CATEGORY_SUMMARY":
      result = ruleCategorySummary(projects, entities);
      break;
    case "TOTAL_ALLOCATION":
      result = ruleTotalAllocation(projects, entities);
      break;
    case "ANOMALY_SUMMARY":
      result = ruleAnomalySummary(projects, entities);
      break;
    case "DUPLICATE_PROJECTS":
      result = ruleDuplicateProjects(projects, entities);
      break;
    case "PROJECT_SEARCH":
    default:
      result = ruleProjectSearch(projects, entities);
      break;
  }

  return {
    question,
    answer: result.answer,
    citations: result.citations,
    intent,
    recordsFound: result.recordsFound,
    safeAuditLanguage: true,
    disclaimer:
      "This assistant applies rule-based statistical analysis over official MPLADS records. Findings surface anomaly indicators for audit review only — they do not constitute fraud determinations. All data is processed locally with no external API calls.",
  };
}
