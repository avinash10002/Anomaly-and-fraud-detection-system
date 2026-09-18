"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AuditAssistantDrawer } from "@/components/AuditAssistantDrawer";
import { useRole } from "@/lib/role-context";

const NAV = [
  { href: "/dashboard", label: "Dashboard", officialOnly: false },
  { href: "/map", label: "Map & Works", officialOnly: false },
  { href: "/review-queue", label: "Review queue", officialOnly: true },
];

export function AppHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const { role, setRole, isCitizen, isOfficial } = useRole();

  const navItems = NAV.filter((item) => !item.officialOnly || isOfficial);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <Link href="/dashboard" className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded bg-brand text-[10px] font-bold tracking-wider text-white">
              MP
            </span>
            <span className="min-w-0">
              <span className="block truncate font-display text-sm font-semibold text-ink">
                MPLAD Anomaly Detector
              </span>
              <span className="hidden text-[11px] text-ink-muted sm:block">
                Fund utilisation monitoring
              </span>
            </span>
          </Link>

          {/* Role Switcher Pill */}
          <div className="hidden sm:flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs">
            <button
              type="button"
              onClick={() => setRole("citizen")}
              className={`rounded px-2.5 py-1 font-medium transition-all ${
                isCitizen
                  ? "bg-white text-ink shadow-sm font-semibold"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              Citizen View
            </button>
            <button
              type="button"
              onClick={() => setRole("official")}
              className={`rounded px-2.5 py-1 font-medium transition-all ${
                isOfficial
                  ? "bg-brand text-white shadow-sm font-semibold"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              Official / Reviewer
            </button>
          </div>

          {/* AI Audit Assistant Launcher */}
          <button
            type="button"
            onClick={() => setAssistantOpen(true)}
            className="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-purple-200 bg-purple-50/90 px-3 py-1 text-xs font-semibold text-purple-900 shadow-sm hover:bg-purple-100 transition-colors"
          >
            <span className="flex h-2 w-2 rounded-full bg-purple-600 animate-pulse" />
            AI Audit Assistant
          </button>

          <button
            type="button"
            className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 text-ink md:hidden"
            aria-expanded={open}
            aria-label="Toggle navigation"
            onClick={() => setOpen((v) => !v)}
          >
            <span className="sr-only">Menu</span>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
              <path
                d="M2 4h12M2 8h12M2 12h12"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>

          <nav
            className={`${
              open ? "flex" : "hidden"
            } absolute left-0 right-0 top-14 flex-col gap-2 border-b border-slate-200 bg-white p-3 shadow-panel md:static md:ml-auto md:flex md:flex-row md:items-center md:gap-1 md:border-0 md:bg-transparent md:p-0 md:shadow-none`}
          >
            {/* Mobile AI Assistant Launcher */}
            <button
              type="button"
              onClick={() => {
                setAssistantOpen(true);
                setOpen(false);
              }}
              className="sm:hidden flex items-center justify-center gap-1.5 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 text-xs font-semibold text-purple-900"
            >
              <span className="flex h-2 w-2 rounded-full bg-purple-600 animate-pulse" />
              Open AI Audit Assistant
            </button>

            {/* Mobile role switcher */}
            <div className="flex sm:hidden items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs mb-2">
              <span className="px-2 text-ink-muted font-medium">Role:</span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setRole("citizen")}
                  className={`rounded px-2.5 py-1 ${
                    isCitizen ? "bg-white text-ink shadow-sm font-semibold" : "text-ink-muted"
                  }`}
                >
                  Citizen
                </button>
                <button
                  type="button"
                  onClick={() => setRole("official")}
                  className={`rounded px-2.5 py-1 ${
                    isOfficial ? "bg-brand text-white shadow-sm font-semibold" : "text-ink-muted"
                  }`}
                >
                  Official
                </button>
              </div>
            </div>

            {navItems.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`rounded px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? "bg-brand/10 text-brand-dark"
                      : "text-ink-muted hover:bg-surface-soft hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Slide-out AI Audit Assistant Drawer */}
      <AuditAssistantDrawer
        isOpen={assistantOpen}
        onClose={() => setAssistantOpen(false)}
      />
    </>
  );
}
