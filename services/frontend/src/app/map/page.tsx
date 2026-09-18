"use client";

import dynamic from "next/dynamic";

const ProjectMap = dynamic(
  () => import("@/components/ProjectMap").then((m) => m.ProjectMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[calc(100dvh-3.5rem-3rem)] items-center justify-center panel text-sm text-ink-muted">
        Loading map…
      </div>
    ),
  }
);

export default function MapPage() {
  return (
    <div className="-mx-4 -my-6 h-[calc(100dvh-3.5rem)] sm:-mx-6">
      <div className="flex h-full flex-col">
        <div className="shrink-0 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
          <h1 className="font-display text-lg font-semibold text-ink">
            Project map
          </h1>
          <p className="text-sm text-ink-muted">
            Markers are colored by risk. Click a marker for summary and details.
          </p>
        </div>
        <div className="min-h-0 flex-1 p-3 sm:p-4">
          <ProjectMap />
        </div>
      </div>
    </div>
  );
}
