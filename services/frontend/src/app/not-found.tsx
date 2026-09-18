import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel p-12 text-center space-y-4">
      <h2 className="font-display text-2xl font-bold text-ink">404 - Page Not Found</h2>
      <p className="text-sm text-ink-muted">The requested page or record could not be found.</p>
      <Link
        href="/dashboard"
        className="inline-block rounded bg-brand px-4 py-2 text-xs font-semibold text-white hover:bg-brand-dark transition-colors"
      >
        ← Return to Dashboard
      </Link>
    </div>
  );
}
