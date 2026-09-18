import type { ProjectImage } from "@/lib/types";
import { formatDate } from "@/lib/format";

export function ImageGalleryPlaceholder({ images }: { images: ProjectImage[] }) {
  if (!images.length) {
    return (
      <p className="rounded border border-dashed border-slate-300 bg-surface-soft px-4 py-8 text-center text-sm text-ink-muted">
        No captured images linked yet.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {images.map((img, index) => (
        <figure key={img.id} className="panel overflow-hidden">
          <div
            className="flex h-36 items-end bg-gradient-to-br from-slate-200 via-slate-100 to-slate-300 p-3"
            aria-hidden
          >
            <span className="rounded bg-white/80 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              {img.source}
            </span>
            <span className="ml-auto font-display text-4xl font-bold text-slate-400/70">
              {String(index + 1).padStart(2, "0")}
            </span>
          </div>
          <figcaption className="space-y-0.5 p-3">
            <p className="text-sm font-medium text-ink">{img.label}</p>
            <p className="text-xs text-ink-muted">{formatDate(img.captureDate)}</p>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
