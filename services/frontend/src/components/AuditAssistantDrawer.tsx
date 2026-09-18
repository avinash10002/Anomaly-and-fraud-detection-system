"use client";

import Link from "next/link";
import { useState } from "react";
import { askAuditAssistant } from "@/lib/api";
import { formatINR } from "@/lib/format";
import { useRole } from "@/lib/role-context";
import type { AuditAssistantResponse } from "@/lib/types";

const SUGGESTIONS = [
  "Show unusually expensive road projects in Punjab",
  "Which constituencies have the most pending projects?",
  "Why was project X flagged?",
];

export function AuditAssistantDrawer({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const { role } = useRole();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AuditAssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (qText?: string) => {
    const q = (qText || question).trim();
    if (!q) return;

    if (qText) {
      setQuestion(qText);
    }

    setLoading(true);
    setError(null);
    try {
      const resp = await askAuditAssistant(q, role);
      setResult(resp);
    } catch (err: any) {
      setError(err?.message || "Failed to query audit assistant.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <aside className="w-screen max-w-xl transform border-l border-slate-200 bg-white shadow-2xl transition-all duration-300 ease-in-out flex flex-col">
          {/* Header */}
          <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-xs font-bold text-white">
                  AI
                </span>
                <div>
                  <h2 className="font-display text-base font-bold text-ink">
                    MPLADS AI Audit Assistant
                  </h2>
                  <p className="text-[11px] text-ink-muted">
                    Safe parameterized query translation over official records
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors"
                aria-label="Close assistant"
              >
                <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </div>

            {/* Quick Suggestion Chips */}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((sug) => (
                <button
                  key={sug}
                  type="button"
                  onClick={() => void handleSubmit(sug)}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:border-brand hover:text-brand transition-colors"
                >
                  {sug}
                </button>
              ))}
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-5">
            {/* Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void handleSubmit();
              }}
              className="space-y-2"
            >
              <div className="relative">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask an audit question (e.g. 'Show unusually expensive road projects in Punjab')..."
                  className="field-control pr-20 text-xs py-2.5"
                />
                <button
                  type="submit"
                  disabled={loading || !question.trim()}
                  className="absolute right-1.5 top-1.5 rounded bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-dark disabled:opacity-50 transition-colors"
                >
                  {loading ? "Analyzing..." : "Ask"}
                </button>
              </div>
            </form>

            {error && (
              <div className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-800">
                {error}
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-brand border-t-transparent" />
                <p className="text-xs text-ink-muted">
                  Translating question into safe parameterized filters & retrieving records…
                </p>
              </div>
            )}

            {/* Results Display */}
            {!loading && result && (
              <div className="space-y-4">
                {/* Answer Card */}
                <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                      Audit Synthesis ({result.intent})
                    </span>
                    <span className="rounded bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                      Grounded in DB ({result.recordsFound} record{result.recordsFound === 1 ? "" : "s"})
                    </span>
                  </div>

                  <p className="whitespace-pre-line text-xs text-ink leading-relaxed font-sans">
                    {result.answer}
                  </p>

                  <div className="border-t border-slate-100 pt-2 text-[11px] text-amber-800 italic">
                    {result.disclaimer}
                  </div>
                </div>

                {/* Citations List */}
                {result.citations.length > 0 && (
                  <div className="space-y-2.5">
                    <h3 className="font-display text-xs font-bold uppercase tracking-wider text-ink-muted">
                      Retrieved Project Citations ({result.citations.length})
                    </h3>

                    <div className="space-y-2">
                      {result.citations.map((c, i) => (
                        <div
                          key={c.projectId || i}
                          className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 hover:bg-slate-50 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              {c.projectId ? (
                                <Link
                                  href={`/dashboard/${c.projectId}`}
                                  className="text-xs font-semibold text-brand hover:underline line-clamp-1"
                                >
                                  {c.title}
                                </Link>
                              ) : (
                                <span className="text-xs font-semibold text-ink">
                                  {c.title}
                                </span>
                              )}
                              <p className="mt-0.5 text-[11px] text-ink-muted">
                                {c.constituency ? `${c.constituency}, ` : ""}
                                {c.state || "—"}
                                {c.category ? ` · ${c.category}` : ""}
                              </p>
                            </div>

                            {c.allocation && (
                              <span className="shrink-0 text-xs font-bold text-ink">
                                {formatINR(c.allocation)}
                              </span>
                            )}
                          </div>

                          {c.flags.length > 0 && (
                            <div className="mt-2 rounded border border-amber-200 bg-amber-50/70 p-2 text-[10px] text-amber-900 leading-normal">
                              <strong>Anomaly Indicator:</strong> {c.flags[0]}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-slate-200 bg-slate-50 px-6 py-3 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Query execution: Zero string-interpolated SQL</span>
            <span className="font-medium">Strict Compliance Guard</span>
          </div>
        </aside>
      </div>
    </div>
  );
}
