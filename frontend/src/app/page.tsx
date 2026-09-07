"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  createRun,
  listRuns,
  listSupervisors,
  type Supervisor,
} from "@/lib/api";
import { Button, Field, StatusBadge, fmtTime, fromNow, inputCls, usePoll } from "@/components/ui";

export default function RunsPage() {
  const { data: runs, error, refresh } = usePoll(() => listRuns(), 3000);

  return (
    <section className="space-y-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">Runs</h1>
        <span className="text-xs text-neutral-500">auto-refresh 3s</span>
      </div>

      <StartRunPanel onStarted={refresh} />

      {error && <p className="text-sm text-red-600">Failed to load runs: {error}</p>}

      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            <th className="py-2">Order</th>
            <th>Status</th>
            <th>Next wake</th>
            <th>Updated</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {runs?.length === 0 && (
            <tr className="border-t border-neutral-200 dark:border-neutral-800">
              <td className="py-3 text-neutral-400" colSpan={5}>
                No runs yet.
              </td>
            </tr>
          )}
          {runs?.map((r) => (
            <tr
              key={r.id}
              className="border-t border-neutral-200 align-top dark:border-neutral-800"
            >
              <td className="py-2 font-mono text-xs">
                <Link href={`/runs/${r.id}`} className="underline decoration-dotted">
                  {r.order_id}
                </Link>
              </td>
              <td className="py-2">
                <StatusBadge status={r.status} />
              </td>
              <td className="py-2 text-neutral-500">
                {r.next_wake_at ? (
                  <span title={fmtTime(r.next_wake_at)}>{fromNow(r.next_wake_at)}</span>
                ) : (
                  "-"
                )}
              </td>
              <td className="py-2 text-neutral-500" title={fmtTime(r.updated_at)}>
                {fromNow(r.updated_at)}
              </td>
              <td className="py-2">
                <Link href={`/runs/${r.id}`} className="text-xs underline">
                  open
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function StartRunPanel({ onStarted }: { onStarted: () => void }) {
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [supervisorId, setSupervisorId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [contextRaw, setContextRaw] = useState('{\n  "sku": "WIDGET-1",\n  "value": 42\n}');
  const [instructionsRaw, setInstructionsRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    listSupervisors()
      .then((s) => {
        setSupervisors(s);
        if (s[0]) setSupervisorId(s[0].id);
      })
      .catch((e) => setMsg({ kind: "err", text: `Could not load supervisors: ${e.message}` }));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    let order_context: Record<string, unknown> = {};
    try {
      order_context = contextRaw.trim() ? JSON.parse(contextRaw) : {};
    } catch {
      setMsg({ kind: "err", text: "order_context is not valid JSON" });
      return;
    }
    const run_instructions = instructionsRaw
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    setBusy(true);
    try {
      const run = await createRun({ supervisor_id: supervisorId, order_id: orderId, order_context, run_instructions });
      setMsg({ kind: "ok", text: `Started run ${run.id}` });
      setOrderId("");
      onStarted();
    } catch (e) {
      const text = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
      setMsg({ kind: "err", text });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded border border-neutral-200 p-4 dark:border-neutral-800 sm:grid-cols-2"
    >
      <h2 className="col-span-full font-medium">Start a run</h2>

      <Field label="Supervisor template">
        <select
          className={inputCls}
          value={supervisorId}
          onChange={(e) => setSupervisorId(e.target.value)}
          required
        >
          {supervisors.length === 0 && <option value="">- none - create one first</option>}
          {supervisors.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Order ID">
        <input
          className={inputCls}
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          placeholder="order-1234"
          required
        />
      </Field>

      <Field label="order_context (JSON)">
        <textarea
          className={inputCls + " h-24 font-mono text-xs"}
          value={contextRaw}
          onChange={(e) => setContextRaw(e.target.value)}
        />
      </Field>

      <Field label="run_instructions (one per line)" hint="extra standing instructions for this run">
        <textarea
          className={inputCls + " h-24 text-xs"}
          value={instructionsRaw}
          onChange={(e) => setInstructionsRaw(e.target.value)}
          placeholder="keep the customer informed"
        />
      </Field>

      <div className="col-span-full flex items-center gap-3">
        <Button type="submit" disabled={busy || !supervisorId || !orderId}>
          {busy ? "Starting..." : "Start run"}
        </Button>
        {msg && (
          <span className={msg.kind === "ok" ? "text-sm text-emerald-600" : "text-sm text-red-600"}>
            {msg.text}
          </span>
        )}
      </div>
    </form>
  );
}
