"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, FormEvent } from "react";
import Link from "next/link";
import { useRole } from "@/lib/role-context";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTarget = searchParams?.get("redirect") || "/review-queue";

  const { isOfficial, official, checkSession, logout } = useRole();

  const [step, setStep] = useState<"email" | "otp">("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(300); // 5 minutes
  const [timerActive, setTimerActive] = useState(false);

  // If already logged in, show status & redirect option
  useEffect(() => {
    if (isOfficial && official) {
      const t = setTimeout(() => {
        router.push(redirectTarget);
      }, 1500);
      return () => clearTimeout(t);
    }
  }, [isOfficial, official, redirectTarget, router]);

  // Countdown timer for OTP
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (timerActive && countdown > 0) {
      interval = setInterval(() => {
        setCountdown((c) => c - 1);
      }, 1000);
    } else if (countdown === 0) {
      setTimerActive(false);
    }
    return () => clearInterval(interval);
  }, [timerActive, countdown]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  async function handleRequestOtp(e?: FormEvent) {
    if (e) e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setError("Please enter a valid official email address.");
      return;
    }

    setLoading(true);
    setError(null);
    setInfoMessage(null);

    try {
      const res = await fetch("/api/auth/request-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.status === 202) {
        setStep("otp");
        setCountdown(300);
        setTimerActive(true);
        setInfoMessage(
          "A 6-digit one-time passcode has been sent to your email. Please check your inbox (and spam folder)."
        );
      } else if (res.status === 429) {
        setError(data.message || "Too many OTP requests. Please wait a few minutes before trying again.");
      } else if (res.status === 423) {
        setError(data.message || "This account is temporarily locked due to repeated failed attempts.");
      } else {
        setError(data.message || "Failed to dispatch verification code. Please try again.");
      }
    } catch {
      setError("Cannot reach authentication service. Please ensure auth-service is active.");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(e: FormEvent) {
    e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    const cleanOtp = otp.trim();

    if (!/^\d{6}$/.test(cleanOtp)) {
      setError("Please enter a valid 6-digit numeric passcode.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: cleanEmail, otp: cleanOtp }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        setInfoMessage("Authentication verified successfully. Redirecting to review workspace...");
        await checkSession();
        router.push(redirectTarget);
      } else if (res.status === 423) {
        setError(data.message || "Account locked due to 5 failed attempts. Please wait 15 minutes.");
      } else if (res.status === 401) {
        if (data.attemptsRemaining !== undefined) {
          setError(`Incorrect passcode. ${data.attemptsRemaining} attempt(s) remaining before account lockout.`);
        } else {
          setError(data.message || "Invalid or expired passcode. Please request a new code.");
        }
      } else {
        setError(data.message || "Verification failed. Please check the code and try again.");
      }
    } catch {
      setError("Authentication service unavailable. Please check backend connection.");
    } finally {
      setLoading(false);
    }
  }

  if (isOfficial && official) {
    return (
      <div className="mx-auto max-w-md py-12">
        <div className="panel p-8 text-center space-y-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 text-2xl font-bold">
            ✓
          </div>
          <h2 className="text-xl font-bold text-ink">Already Signed In</h2>
          <p className="text-sm text-ink-muted">
            You are authenticated as{" "}
            <strong className="text-ink font-semibold">{official.name}</strong> (
            <span className="capitalize text-brand font-medium">{official.role}</span>).
          </p>
          <div className="pt-2 flex flex-col gap-2">
            <Link
              href={redirectTarget}
              className="btn btn-primary w-full justify-center"
            >
              Continue to Workspace
            </Link>
            <button
              type="button"
              onClick={() => logout()}
              className="btn btn-ghost w-full justify-center text-xs text-red-600 hover:text-red-700"
            >
              Sign Out from this account
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg py-8 sm:py-12">
      {/* Emblemed Header */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-brand text-white shadow-md mb-3 font-bold text-sm tracking-wider">
          GOI
        </div>
        <div className="text-[11px] font-semibold uppercase tracking-widest text-brand-dark/80">
          Government of India • MoSPI
        </div>
        <h1 className="mt-1 font-display text-2xl font-bold text-ink">
          Official Reviewer Login
        </h1>
        <p className="mt-1 text-xs text-ink-muted">
          MPLADS Anomaly Detection &amp; Audit Workspace
        </p>
      </div>

      {/* Main Login Card */}
      <div className="panel p-6 sm:p-8 bg-white shadow-md border-slate-200">
        {/* Security Notice */}
        <div className="mb-6 rounded border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-900 flex items-start gap-2.5">
          <span className="text-base leading-none">🔒</span>
          <div>
            <strong className="font-semibold block mb-0.5">Authorized Personnel Only</strong>
            Access is restricted to pre-registered MPLADS project reviewers and audit officers.
            Passcodes are delivered directly to verified email addresses.
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded border border-red-200 bg-red-50 p-3 text-xs text-red-800 flex items-start gap-2">
            <span className="font-bold">⚠️</span>
            <div className="flex-1">{error}</div>
          </div>
        )}

        {infoMessage && (
          <div className="mb-4 rounded border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900 flex items-start gap-2">
            <span className="font-bold">ℹ️</span>
            <div className="flex-1">{infoMessage}</div>
          </div>
        )}

        {step === "email" ? (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div>
              <label htmlFor="official-email" className="field-label">
                Official Registered Email Address
              </label>
              <input
                id="official-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="officer@mplads.gov.in"
                className="field-control text-base sm:text-sm"
                disabled={loading}
              />
              <p className="mt-1 text-[11px] text-ink-muted">
                Enter your pre-registered government or official audit email.
              </p>
            </div>

            {/* Quick-fill Demo Accounts */}
            <div className="pt-2 border-t border-slate-100">
              <span className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Pre-registered Demo Accounts (Click to test):
              </span>
              <div className="flex flex-col sm:flex-row gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setEmail("avinahgoel12@gmail.com");
                    setError(null);
                  }}
                  className="flex-1 text-left px-2.5 py-1.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-brand/40 transition text-xs"
                >
                  <div className="font-semibold text-ink flex items-center justify-between">
                    <span>Avinash Goel</span>
                    <span className="text-[10px] px-1 rounded bg-purple-100 text-purple-800 font-bold">Admin</span>
                  </div>
                  <div className="text-[11px] text-ink-muted truncate">avinahgoel12@gmail.com</div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setEmail("avinashgoel6654@gmail.com");
                    setError(null);
                  }}
                  className="flex-1 text-left px-2.5 py-1.5 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-brand/40 transition text-xs"
                >
                  <div className="font-semibold text-ink flex items-center justify-between">
                    <span>Avinash Goel</span>
                    <span className="text-[10px] px-1 rounded bg-blue-100 text-blue-800 font-bold">Reviewer</span>
                  </div>
                  <div className="text-[11px] text-ink-muted truncate">avinashgoel6654@gmail.com</div>
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !email.trim()}
              className="btn btn-primary w-full py-2.5 mt-2 justify-center font-semibold text-sm"
            >
              {loading ? "Sending Passcode…" : "Send Verification Passcode"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <div className="rounded bg-slate-50 border border-slate-200 p-3 flex items-center justify-between text-xs">
              <div className="truncate">
                <span className="text-ink-muted block text-[11px]">Recipient Email:</span>
                <strong className="text-ink font-semibold truncate block">{email}</strong>
              </div>
              <button
                type="button"
                onClick={() => {
                  setStep("email");
                  setOtp("");
                  setError(null);
                  setInfoMessage(null);
                }}
                className="text-brand hover:underline font-semibold shrink-0 ml-2"
              >
                Change
              </button>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="otp-input" className="field-label">
                  Enter 6-Digit Passcode
                </label>
                <span className="text-xs font-mono font-medium text-slate-500">
                  Expires in: <strong className={countdown < 60 ? "text-red-600" : "text-slate-700"}>{formatTime(countdown)}</strong>
                </span>
              </div>
              <input
                id="otp-input"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                autoFocus
                required
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="• • • • • •"
                className="field-control text-center tracking-[0.5em] font-mono text-xl py-3 font-bold"
                disabled={loading}
              />
              <p className="mt-1.5 text-[11px] text-ink-muted text-center">
                Never share your login code with anyone.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading || otp.length !== 6}
              className="btn btn-primary w-full py-2.5 justify-center font-semibold text-sm"
            >
              {loading ? "Verifying…" : "Sign In to Audit Workspace"}
            </button>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs text-ink-muted">
              <span>Didn’t receive the code?</span>
              <button
                type="button"
                disabled={loading || timerActive}
                onClick={() => handleRequestOtp()}
                className={`font-semibold ${
                  timerActive ? "text-slate-400 cursor-not-allowed" : "text-brand hover:underline"
                }`}
              >
                {timerActive ? `Resend code in ${formatTime(countdown)}` : "Resend Passcode"}
              </button>
            </div>
          </form>
        )}

        <div className="mt-6 pt-4 border-t border-slate-100 text-center">
          <Link
            href="/dashboard"
            className="text-xs text-ink-muted hover:text-ink font-medium"
          >
            ← Return to Citizen Dashboard
          </Link>
        </div>
      </div>

      <div className="mt-6 text-center text-xs text-slate-400">
        MPLADS Fund Monitoring &amp; Oversight System • NIC / Government of India
      </div>
    </div>
  );
}
