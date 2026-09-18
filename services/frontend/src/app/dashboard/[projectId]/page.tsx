import Link from "next/link";
import { notFound } from "next/navigation";
import { AnomalyFlagList } from "@/components/AnomalyFlagList";
import { ImageGalleryPlaceholder } from "@/components/ImageGalleryPlaceholder";
import { ProjectTimeline } from "@/components/ProjectTimeline";
import { RiskBadge } from "@/components/RiskBadge";
import {
  getAnomalyFlags,
  getProjectById,
  getProjectImages,
} from "@/lib/api";
import { formatDate, formatINR } from "@/lib/format";

export default async function ProjectDetailPage({
  params,
}: {
  params: { projectId: string };
}) {
  const project = await getProjectById(params.projectId);
  if (!project) notFound();

  const [flags, images] = await Promise.all([
    getAnomalyFlags(project.id),
    getProjectImages(project.id),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard"
          className="text-sm font-medium text-brand hover:underline"
        >
          ← Back to dashboard
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl">
            <h1 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              {project.title}
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              {project.district} · {project.contractorName}
            </p>
          </div>
          <RiskBadge level={project.riskLevel} score={project.riskScore} />
        </div>
      </div>

      <section className="panel grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
        <Info label="Type" value={project.type} capitalize />
        <Info label="Status" value={project.status} capitalize />
        <Info label="Cost" value={formatINR(project.cost)} />
        <Info label="Sanction date" value={formatDate(project.sanctionDate)} />
        <Info
          label="Completion date"
          value={formatDate(project.completionDate)}
        />
        <Info label="MP" value={project.mpName} />
        <Info
          label="Coordinates"
          value={`${project.lat.toFixed(4)}, ${project.lng.toFixed(4)}`}
        />
        <Info label="Anomaly flags" value={String(project.anomalyCount)} />
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section className="panel p-4">
          <h2 className="font-display text-base font-semibold text-ink">
            Timeline
          </h2>
          <p className="mb-4 mt-1 text-xs text-ink-muted">
            Sanction → flags → declared completion
          </p>
          <ProjectTimeline
            sanctionDate={project.sanctionDate}
            completionDate={project.completionDate}
            flags={flags}
          />
        </section>

        <section>
          <h2 className="mb-3 font-display text-base font-semibold text-ink">
            Anomaly flags
          </h2>
          <AnomalyFlagList flags={flags} />
        </section>
      </div>

      <section>
        <h2 className="mb-3 font-display text-base font-semibold text-ink">
          Image gallery
        </h2>
        <p className="mb-3 text-sm text-ink-muted">
          Placeholder tiles for captured imagery over time (Street View /
          Mapillary / upload).
        </p>
        <ImageGalleryPlaceholder images={images} />
      </section>
    </div>
  );
}

function Info({
  label,
  value,
  capitalize = false,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div>
      <dt className="field-label">{label}</dt>
      <dd className={`text-sm font-medium text-ink ${capitalize ? "capitalize" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
