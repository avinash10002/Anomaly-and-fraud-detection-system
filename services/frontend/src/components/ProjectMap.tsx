"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  Marker,
  TileLayer,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { RiskBadge, riskMarkerColor } from "@/components/RiskBadge";
import { getProjects } from "@/lib/api";
import { formatINR } from "@/lib/format";
import type { ProjectWithRisk } from "@/lib/types";

function makeIcon(color: string) {
  return L.divIcon({
    className: "",
    html: `<span style="display:block;width:14px;height:14px;border-radius:3px;background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35)"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function FitBounds({ projects }: { projects: ProjectWithRisk[] }) {
  const map = useMap();
  useEffect(() => {
    if (!projects.length) return;
    const bounds = L.latLngBounds(projects.map((p) => [p.lat, p.lng]));
    map.fitBounds(bounds.pad(0.2));
  }, [map, projects]);
  return null;
}

export function ProjectMap() {
  const [projects, setProjects] = useState<ProjectWithRisk[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const list = await getProjects();
      if (!cancelled) {
        setProjects(list);
        setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => projects.find((p) => p.id === selectedId) ?? null,
    [projects, selectedId]
  );

  if (!ready) {
    return (
      <div className="flex h-[calc(100dvh-3.5rem-3rem)] items-center justify-center panel text-sm text-ink-muted">
        Loading map…
      </div>
    );
  }

  return (
    <div className="relative h-[calc(100dvh-3.5rem-3rem)] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-panel">
      <MapContainer
        center={[22.5, 78.5]}
        zoom={5}
        className="h-full w-full"
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds projects={projects} />
        {projects.map((p) => (
          <Marker
            key={p.id}
            position={[p.lat, p.lng]}
            icon={makeIcon(riskMarkerColor(p.riskLevel))}
            eventHandlers={{
              click: () => setSelectedId(p.id),
            }}
          />
        ))}
      </MapContainer>

      <aside
        className={`absolute inset-y-0 right-0 z-[500] w-full max-w-sm transform border-l border-slate-200 bg-white p-4 shadow-panel transition-transform duration-200 ease-out sm:w-96 ${
          selected ? "translate-x-0" : "translate-x-full"
        }`}
        aria-hidden={!selected}
      >
        {selected ? (
          <div className="flex h-full flex-col gap-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Project summary
                </p>
                <h2 className="mt-1 font-display text-lg font-semibold leading-snug text-ink">
                  {selected.title}
                </h2>
              </div>
              <button
                type="button"
                className="btn-ghost shrink-0 px-2 py-1 text-xs"
                onClick={() => setSelectedId(null)}
              >
                Close
              </button>
            </div>

            <RiskBadge level={selected.riskLevel} score={selected.riskScore} />

            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="field-label">District</dt>
                <dd className="font-medium">{selected.district}</dd>
              </div>
              <div>
                <dt className="field-label">Type</dt>
                <dd className="font-medium capitalize">{selected.type}</dd>
              </div>
              <div>
                <dt className="field-label">Status</dt>
                <dd className="font-medium capitalize">{selected.status}</dd>
              </div>
              <div>
                <dt className="field-label">Cost</dt>
                <dd className="font-medium tabular-nums">
                  {formatINR(selected.cost)}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="field-label">Contractor</dt>
                <dd className="font-medium">{selected.contractorName}</dd>
              </div>
              <div className="col-span-2">
                <dt className="field-label">MP</dt>
                <dd className="font-medium">{selected.mpName}</dd>
              </div>
            </dl>

            <Link
              href={`/dashboard/${selected.id}`}
              className="btn-primary mt-auto w-full"
            >
              View details
            </Link>
          </div>
        ) : null}
      </aside>

      <div className="pointer-events-none absolute left-3 top-3 z-[400] rounded border border-slate-200 bg-white/95 px-3 py-2 text-xs text-ink shadow-sm">
        <p className="font-semibold">Risk markers</p>
        <ul className="mt-1 space-y-1">
          <li className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm bg-risk-high" /> High &gt;0.7
          </li>
          <li className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm bg-risk-mid" /> Medium 0.3–0.7
          </li>
          <li className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm bg-risk-low" /> Low &lt;0.3
          </li>
        </ul>
      </div>
    </div>
  );
}
