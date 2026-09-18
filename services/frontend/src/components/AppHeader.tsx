"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const { role, setRole, isCitizen, isOfficial, official, logout } = useRole();

  const navItems = NAV.filter((item) => !item.officialOnly || isOfficial);

  function handleOfficialClick() {
    if (official) {
      setRole("official");
    } else {
      router.push("/login?redirect=/review-queue");
    }
  }

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
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
              onClick={handleOfficialClick}
              className={`rounded px-2.5 py-1 font-medium transition-all flex items-center gap-1.5 ${
                isOfficial
                  ? "bg-brand text-white shadow-sm font-semibold"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {!official && <span className="text-[11px]">🔒</span>}
              Official / Reviewer
            </button>
          </div>

          {/* Official Profile Badge or Login Button */}
          {official ? (
            <div className="hidden lg:flex items-center gap-2 pl-1 border-l border-slate-200 text-xs">
              <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="font-semibold text-ink max-w-[120px] truncate">{official.name}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded font-bold uppercase ${
                    official.role === "admin"
                      ? "bg-purple-100 text-purple-800"
                      : "bg-blue-100 text-blue-800"
                  }`}
                >
                  {official.role}
                </span>
              </div>
              <button
                type="button"
                onClick={() => logout()}
                className="text-[11px] font-semibold text-red-600 hover:text-red-800 hover:underline px-1 py-1"
                title="Sign out of official account"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="hidden sm:inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-ink shadow-sm hover:bg-slate-50 transition-colors"
            >
              <span>🔒</span>
              Official Login
            </Link>
          )}

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

            {/* Mobile official status or login */}
            {official ? (
              <div className="sm:hidden flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs">
                <div>
                  <span className="font-semibold text-ink block">{official.name}</span>
                  <span className="text-[10px] text-brand font-medium uppercase">{official.role}</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    setOpen(false);
                  }}
                  className="font-semibold text-red-600 hover:underline"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                onClick={() => setOpen(false)}
                className="sm:hidden flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-ink"
              >
                <span>🔒</span>
                Official Login
              </Link>
            )}

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
