"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  Marker,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { RiskBadge, riskMarkerColor } from "@/components/RiskBadge";
import {
  getAdministrativeHierarchy,
  getGeocodedProjects,
  getWorksNearMe,
} from "@/lib/api";
import { formatINR } from "@/lib/format";
import { useRole } from "@/lib/role-context";
import type {
  AdministrativeHierarchy,
  ProjectWithRisk,
  RiskLevel,
} from "@/lib/types";

function makeIcon(color: string) {
  return L.divIcon({
    className: "leaflet-div-icon anomaly-map-marker",
    html: `<span style="display:block;width:16px;height:16px;border-radius:50%;background:${color};border:2px solid #ffffff;box-shadow:0 2px 6px rgba(0,0,0,0.5)"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -10],
  });
}

function FitBounds({
  projects,
  selectedProject,
}: {
  projects: ProjectWithRisk[];
  selectedProject: ProjectWithRisk | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (
      selectedProject &&
      typeof selectedProject.lat === "number" &&
      typeof selectedProject.lng === "number"
    ) {
      map.setView([selectedProject.lat, selectedProject.lng], 10, {
        animate: true,
      });
      return;
    }

    const geoProjects = projects.filter(
      (p) => typeof p.lat === "number" && typeof p.lng === "number"
    );
    if (!geoProjects.length) {
      map.setView([22.9734, 78.6569], 5);
      return;
    }

    if (geoProjects.length === 1) {
      map.setView([geoProjects[0].lat as number, geoProjects[0].lng as number], 10);
      return;
    }

    const bounds = L.latLngBounds(
      geoProjects.map((p) => [p.lat as number, p.lng as number] as [number, number])
    );
    map.fitBounds(bounds.pad(0.15), { maxZoom: 12 });
  }, [map, projects, selectedProject]);

  return null;
}

function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    const timers = [50, 200, 600].map((ms) =>
      window.setTimeout(() => map.invalidateSize(), ms)
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [map]);
  return null;
}

export function ProjectMap() {
  const { role, isCitizen } = useRole();

  // Mode: "all" for full national / state explorer, "nearme" for 5 seeded demo cases
  const [viewMode, setViewMode] = useState<"all" | "nearme">("all");

  const [adminData, setAdminData] = useState<AdministrativeHierarchy>({
    states: [],
    constituenciesByState: {},
  });

  // Filters
  const [selectedState, setSelectedState] = useState<string>("");
  const [selectedConstituency, setSelectedConstituency] = useState<string>("");
  const [selectedRisk, setSelectedRisk] = useState<RiskLevel | "">("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Projects displayed on the map
  const [mapProjects, setMapProjects] = useState<ProjectWithRisk[]>([]);
  const [demoProjects, setDemoProjects] = useState<ProjectWithRisk[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [showListTray, setShowListTray] = useState<boolean>(false);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mapKey, setMapKey] = useState(0);

  // 1. Initial Load: Administrative Hierarchy & Demo Cases
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [hierarchy, demos] = await Promise.all([
          getAdministrativeHierarchy(),
          getWorksNearMe(role),
        ]);
        if (cancelled) return;
        setAdminData(hierarchy);
        setDemoProjects(demos);
        setReady(true);
      } catch {
        if (!cancelled) {
          setLoadError("Unable to load geographic and administrative data.");
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [role]);

  // 2. Fetch/Filter geocoded projects whenever filters or viewMode changes
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        if (viewMode === "nearme") {
          const demos = await getWorksNearMe(role);
          if (cancelled) return;
          setMapProjects(demos);
          setSelectedProjectId(demos[0]?.id ?? null);
          setLoading(false);
        } else {
          const fetched = await getGeocodedProjects(
            {
              state: selectedState || undefined,
              constituency: selectedConstituency || undefined,
              riskLevel: selectedRisk || undefined,
              search: searchQuery || undefined,
            },
            role
          );
          if (cancelled) return;
          setMapProjects(fetched);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [viewMode, selectedState, selectedConstituency, selectedRisk, searchQuery, role, ready]);

  // Available constituencies for currently selected state
  const availableConstituencies = useMemo(() => {
    if (!selectedState) {
      const all = Object.values(adminData.constituenciesByState).flat();
      return Array.from(new Set(all)).sort();
    }
    return adminData.constituenciesByState[selectedState] || [];
  }, [selectedState, adminData]);

  // Handle state change
  const handleStateChange = (st: string) => {
    setSelectedState(st);
    setSelectedConstituency("");
    setSelectedProjectId(null);
    setMapKey((k) => k + 1);
  };

  // Selected project object for inspector drawer
  const selectedProject = useMemo(() => {
    if (!selectedProjectId) return null;
    return (
      mapProjects.find((p) => p.id === selectedProjectId) ||
      demoProjects.find((p) => p.id === selectedProjectId) ||
      null
    );
  }, [mapProjects, demoProjects, selectedProjectId]);

  // Projects with valid numeric coordinates
  const validGeoProjects = useMemo(() => {
    return mapProjects.filter(
      (p) => typeof p.lat === "number" && typeof p.lng === "number"
    );
  }, [mapProjects]);

  if (!ready) {
    return (
      <div className="flex h-full min-h-[480px] items-center justify-center panel text-sm text-ink-muted">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
          <span>Loading interactive geographic explorer…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col space-y-3">
      {loadError && (
        <div className="shrink-0 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {loadError}
        </div>
      )}

      {/* Top Filter & Navigation Bar */}
      <div className="flex shrink-0 flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
        {/* Row 1: Mode Switcher & Statistics */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setViewMode("all");
                setMapKey((k) => k + 1);
              }}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                viewMode === "all"
                  ? "bg-brand text-white shadow-sm"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              🇮🇳 All India / State Explorer
            </button>
            <button
              type="button"
              onClick={() => {
                setViewMode("nearme");
                setMapKey((k) => k + 1);
              }}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                viewMode === "nearme"
                  ? "bg-amber-600 text-white shadow-sm"
                  : "bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100"
              }`}
            >
              🔬 5 Seeded Demo Cases (Defect Timelines)
            </button>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 font-medium text-slate-700 border border-slate-200">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <strong>{validGeoProjects.length}</strong> pin points plotted
              {isCitizen ? " · Citizen view" : ""}
            </span>

            <button
              type="button"
              onClick={() => setShowListTray((prev) => !prev)}
              className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-ink hover:bg-slate-100"
            >
              {showListTray ? "Hide Project List" : "Show Project List"}
            </button>
          </div>
        </div>

        {/* Row 2: Dynamic Filters (Available in All India Mode) */}
        {viewMode === "all" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 pt-1 text-xs">
            {/* State Filter */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                State ({adminData.states.length})
              </label>
              <select
                value={selectedState}
                onChange={(e) => handleStateChange(e.target.value)}
                className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-2.5 py-1.5 text-xs text-ink focus:border-brand focus:bg-white focus:outline-none"
              >
                <option value="">All States / Nationwide</option>
                {adminData.states.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>

            {/* Constituency Filter */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Parliamentary Constituency
              </label>
              <select
                value={selectedConstituency}
                onChange={(e) => {
                  setSelectedConstituency(e.target.value);
                  setSelectedProjectId(null);
                }}
                className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-2.5 py-1.5 text-xs text-ink focus:border-brand focus:bg-white focus:outline-none"
              >
                <option value="">All Constituencies</option>
                {availableConstituencies.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* Risk Level Filter */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Risk Level
              </label>
              <select
                value={selectedRisk}
                onChange={(e) => {
                  setSelectedRisk(e.target.value as RiskLevel | "");
                  setSelectedProjectId(null);
                }}
                className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-2.5 py-1.5 text-xs text-ink focus:border-brand focus:bg-white focus:outline-none"
              >
                <option value="">All Risk Levels</option>
                <option value="high">🔴 High Risk (Anomalies)</option>
                <option value="medium">🟡 Medium Risk</option>
                <option value="low">🟢 Low Risk</option>
              </select>
            </div>

            {/* Keyword Search */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Search Work or MP
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="e.g., road, bridge, Kaswan..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-2.5 py-1.5 text-xs text-ink focus:border-brand focus:bg-white focus:outline-none"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-1.5 text-slate-400 hover:text-slate-600"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {viewMode === "nearme" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-900 flex items-center justify-between">
            <p>
              <strong>Seeded Demo Mode:</strong> Exploring the 5 verified reference cases with synthetic chronological defect timelines and anomaly signatures.
            </p>
            <span className="rounded bg-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-900">
              5 DEMO CASES ACTIVE
            </span>
          </div>
        )}
      </div>

      {/* Main Interactive Map & Inspector Layout */}
      <div className="relative min-h-[460px] flex-1 overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-panel flex">
        {/* Map Container */}
        <div className="relative h-full w-full flex-1">
          {loading && (
            <div className="absolute top-3 right-3 z-[450] rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-brand shadow backdrop-blur flex items-center gap-2">
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-brand border-t-transparent" />
              <span>Updating pins…</span>
            </div>
          )}

          {validGeoProjects.length > 0 ? (
            <MapContainer
              key={mapKey}
              center={[22.9734, 78.6569]}
              zoom={5}
              className="h-full w-full"
              style={{ height: "100%", width: "100%", minHeight: 460 }}
              scrollWheelZoom
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <InvalidateSize />
              <FitBounds
                projects={validGeoProjects}
                selectedProject={selectedProject}
              />
              {validGeoProjects.map((p) => {
                const isSelected = p.id === selectedProjectId;
                const markerColor = riskMarkerColor(p.riskLevel);
                return (
                  <Marker
                    key={p.id}
                    position={[p.lat as number, p.lng as number]}
                    icon={makeIcon(markerColor)}
                    eventHandlers={{
                      click: () => setSelectedProjectId(p.id),
                    }}
                  >
                    <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
                      <div className="text-xs p-1 max-w-xs">
                        <p className="font-bold text-slate-900 truncate">{p.title}</p>
                        <p className="text-[11px] text-slate-600 mt-0.5">
                          {p.constituency || p.district}, {p.state}
                        </p>
                        <p className="text-[11px] font-semibold text-brand mt-0.5">
                          {formatINR(p.cost)} · <span className="capitalize">{p.riskLevel} Risk</span>
                        </p>
                      </div>
                    </Tooltip>
                  </Marker>
                );
              })}
            </MapContainer>
          ) : (
            <div className="flex h-full min-h-[460px] flex-col items-center justify-center bg-slate-50 p-6 text-center">
              <p className="text-base font-semibold text-slate-800">
                No developmental works match your current filters.
              </p>
              <p className="mt-1 text-xs text-slate-500 max-w-sm">
                Try resetting your state, constituency, or search query to view project markers across India.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSelectedState("");
                  setSelectedConstituency("");
                  setSelectedRisk("");
                  setSearchQuery("");
                }}
                className="mt-4 rounded-lg bg-brand px-4 py-2 text-xs font-semibold text-white shadow hover:bg-brand-dark transition-all"
              >
                Reset All Filters
              </button>
            </div>
          )}
        </div>

        {/* Slide-Out Inspector Drawer */}
        <aside
          className={`absolute inset-y-0 right-0 z-[500] w-full max-w-sm transform border-l border-slate-200 bg-white p-4 shadow-2xl transition-transform duration-200 ease-out sm:w-96 ${
            selectedProject ? "translate-x-0" : "translate-x-full pointer-events-none"
          }`}
        >
          {selectedProject && (
            <div className="flex h-full flex-col justify-between overflow-y-auto">
              <div className="space-y-3.5">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                  {selectedProject.sourceType === "DEMO_SYNTHETIC" ? (
                    <span className="rounded bg-amber-100 border border-amber-300 px-2 py-0.5 text-[10px] font-bold text-amber-800 uppercase tracking-wide">
                      DEMO SYNTHETIC TIMELINE
                    </span>
                  ) : (
                    <span className="rounded bg-sky-100 border border-sky-300 px-2 py-0.5 text-[10px] font-bold text-sky-800 uppercase tracking-wide">
                      MPLADS OFFICIAL RECORD
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setSelectedProjectId(null)}
                    className="rounded p-1 text-slate-400 hover:text-slate-700 font-bold"
                  >
                    ✕
                  </button>
                </div>

                {/* Title */}
                <div>
                  <h3 className="font-display text-base font-bold text-ink leading-snug">
                    {selectedProject.title}
                  </h3>
                  {selectedProject.workDescription &&
                    selectedProject.workDescription !== selectedProject.title && (
                      <p className="mt-1 text-xs text-slate-600 line-clamp-3">
                        {selectedProject.workDescription}
                      </p>
                    )}
                </div>

                {/* Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <RiskBadge
                    level={selectedProject.riskLevel}
                    score={selectedProject.riskScore}
                  />
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-medium text-slate-700 capitalize">
                    {selectedProject.status}
                  </span>
                  <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-medium text-blue-700">
                    {selectedProject.category || selectedProject.type}
                  </span>
                </div>

                {/* Details Table */}
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2 text-xs">
                  <div>
                    <span className="text-slate-500">Sanctioned Amount: </span>
                    <span className="font-bold text-slate-900">
                      {formatINR(selectedProject.cost)}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500">State & Constituency: </span>
                    <span className="font-medium text-slate-900">
                      {selectedProject.constituency || selectedProject.district},{" "}
                      {selectedProject.state}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500">Elected MP: </span>
                    <span className="font-medium text-slate-900">
                      {selectedProject.mpName}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500">Implementing Agency: </span>
                    <span className="font-medium text-slate-900">
                      {selectedProject.contractorName}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-500">GPS Coordinates: </span>
                    <span className="font-mono text-[11px] text-slate-800">
                      {selectedProject.lat?.toFixed(4)}, {selectedProject.lng?.toFixed(4)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="pt-4 border-t border-slate-100">
                <Link
                  href={`/dashboard/${selectedProject.id}`}
                  className="block w-full text-center rounded-lg bg-brand py-2.5 text-xs font-bold text-white shadow hover:bg-brand-dark transition-colors"
                >
                  View Full Audit Details & Analysis →
                </Link>
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Optional Collapsible Project List Tray */}
      {showListTray && (
        <div className="max-h-60 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3 shadow-panel">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-2">
            <h4 className="font-display text-xs font-bold text-slate-800">
              Matching Projects on Map ({validGeoProjects.length})
            </h4>
            <span className="text-[11px] text-slate-500">Click any row to jump to pin</span>
          </div>

          <div className="divide-y divide-slate-100 text-xs">
            {validGeoProjects.slice(0, 50).map((p) => (
              <div
                key={p.id}
                onClick={() => setSelectedProjectId(p.id)}
                className={`flex items-center justify-between py-2 px-2 cursor-pointer rounded transition-colors ${
                  selectedProjectId === p.id
                    ? "bg-brand/10 font-semibold text-brand"
                    : "hover:bg-slate-50"
                }`}
              >
                <div className="min-w-0 flex-1 pr-3">
                  <p className="truncate font-medium text-slate-900">{p.title}</p>
                  <p className="text-[11px] text-slate-500 truncate">
                    {p.constituency || p.district}, {p.state} · MP: {p.mpName}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="font-bold text-slate-900">{formatINR(p.cost)}</span>
                  <RiskBadge level={p.riskLevel} score={p.riskScore} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
