"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RunStatus } from "@/lib/api";

// Polling hook: re-runs `fn` every `ms` and on demand.
export function usePoll<T>(fn: () => Promise<T>, ms = 3000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const refresh = useCallback(async () => {
    try {
      const next = await fnRef.current();
      setData(next);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, ms);
    return () => clearInterval(id);
  }, [refresh, ms]);

  return { data, error, loading, refresh };
}

// Small shared bits.
export function Button({
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={
        "rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium " +
        "hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-50 " +
        "dark:border-neutral-700 dark:bg-neutral-900 dark:hover:bg-neutral-800 " +
        className
      }
    />
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="font-medium text-neutral-700 dark:text-neutral-300">{label}</span>
      {children}
      {hint && <span className="block text-xs text-neutral-500">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "w-full rounded border border-neutral-300 bg-white px-2 py-1 text-sm " +
  "focus:outline-none focus:ring-1 focus:ring-neutral-400 " +
  "dark:border-neutral-700 dark:bg-neutral-950";

const STATUS_COLORS: Record<RunStatus | string, string> = {
  active: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  sleeping: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  completed: "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  terminated: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={
        "inline-block rounded px-1.5 py-0.5 text-xs font-medium " +
        (STATUS_COLORS[status] ?? "bg-neutral-200 text-neutral-700")
      }
    >
      {status}
    </span>
  );
}

// Time helpers.
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { hour12: false });
}

export function fromNow(iso: string | null | undefined): string {
  if (!iso) return "-";
  const diff = new Date(iso).getTime() - Date.now();
  const s = Math.round(diff / 1000);
  const abs = Math.abs(s);
  const unit =
    abs < 60 ? [s, "s"] : abs < 3600 ? [s / 60, "m"] : abs < 86400 ? [s / 3600, "h"] : [s / 86400, "d"];
  const n = Math.round(unit[0] as number);
  return s >= 0 ? `in ${n}${unit[1]}` : `${-n}${unit[1]} ago`;
}
