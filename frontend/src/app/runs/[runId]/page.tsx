"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  EVENT_TYPES,
  addInstruction,
  getRun,
  injectEvent,
  interruptRun,
  type ActivityLogRow,
} from "@/lib/api";
import { Button, Field, StatusBadge, fmtTime, fromNow, inputCls, usePoll } from "@/components/ui";

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data, error, refresh } = usePoll(() => getRun(runId), 3000);

  const run = data?.run;
  const live = data?.live ?? null;
  const timeline = data?.timeline ?? [];
  const done = run?.status === "completed" || run?.status === "terminated";

  const finalRow = useMemo(
    () => [...timeline].reverse().find((a) => a.type === "final_output"),
    [timeline],
  );

  return (
    <section className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="text-sm underline">
          &larr; runs
        </Link>
        <h1 className="text-lg font-semibold">
          {run ? run.order_id : runId}
          {run && <span className="ml-2 align-middle"><StatusBadge status={run.status} /></span>}
        </h1>
      </div>

      {error && <p className="text-sm text-red-600">Failed to load run: {error}</p>}

      <div className="grid gap-8 lg:grid-cols-[1.8fr_1fr]">
        {/* -------- left: state + timeline -------- */}
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 rounded border border-neutral-200 p-4 text-sm dark:border-neutral-800 sm:grid-cols-3">
            <Meta label="status" value={run?.status ?? "-"} />
            <Meta
              label="next wake"
              value={
                run?.next_wake_at
                  ? `${fromNow(run.next_wake_at)} (${fmtTime(run.next_wake_at)})`
                  : "-"
              }
            />
            <Meta label="updated" value={fmtTime(run?.updated_at)} />
            <Meta label="queued events" value={live ? String(live.queued_events) : "?"} />
            <Meta label="agent wakes" value={live ? String(live.processed_wakes) : "?"} />
            <Meta label="terminating" value={live ? String(live.terminating) : "?"} />
            <Meta
              label="workflow id"
              value={run?.workflow_id ?? "-"}
              mono
              className="col-span-full"
            />
            {live && live.standing_instructions.length > 0 && (
              <Meta
                label="standing instructions"
                value={live.standing_instructions.join(" | ")}
                className="col-span-full"
              />
            )}
          </div>

          <div>
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
              Memory summary
            </h2>
            <pre className="whitespace-pre-wrap rounded bg-neutral-100 p-3 text-xs dark:bg-neutral-900">
              {live?.memory_summary || run?.memory_summary || "(empty)"}
            </pre>
          </div>

          {finalRow && (
            <div>
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
                Final output
              </h2>
              <FinalOutput payload={finalRow.payload} />
            </div>
          )}

          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
              Timeline ({timeline.length})
            </h2>
            <ol className="space-y-2">
              {timeline.length === 0 && <li className="text-sm text-neutral-400">(nothing yet)</li>}
              {[...timeline].reverse().map((a) => (
                <TimelineItem key={a.id} row={a} />
              ))}
            </ol>
          </div>
        </div>

        {/* -------- right: control panel -------- */}
        <aside className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Control panel
          </h2>
          {done && (
            <p className="rounded bg-neutral-100 p-2 text-xs text-neutral-500 dark:bg-neutral-900">
              Run is {run?.status}. Signals are disabled.
            </p>
          )}
          <InjectEventCard runId={runId} disabled={done} onDone={refresh} />
          <InstructionCard runId={runId} disabled={done} onDone={refresh} />
          <InterruptCard runId={runId} disabled={done} onDone={refresh} />
        </aside>
      </div>
    </section>
  );
}

function Meta({
  label,
  value,
  mono,
  className = "",
}: {
  label: string;
  value: string;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className={mono ? "break-all font-mono text-xs" : "text-sm"}>{value}</div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Timeline rendering
// --------------------------------------------------------------------------- //
const TYPE_STYLE: Record<string, string> = {
  incoming_event: "border-l-indigo-400",
  wake_decision: "border-l-sky-400",
  agent_action: "border-l-emerald-400",
  manual_instruction: "border-l-amber-400",
  final_output: "border-l-neutral-400",
};

function TimelineItem({ row }: { row: ActivityLogRow }) {
  const p = row.payload as Record<string, unknown>;
  const s = (k: string, fallback = "?") => (p[k] == null ? fallback : String(p[k]));
  let headline: string = row.type;
  if (row.type === "incoming_event") headline = `event: ${s("type")}`;
  else if (row.type === "wake_decision")
    headline =
      p.stage === "classifier"
        ? `classifier: ${p.wake_now ? "WAKE" : "stay asleep"} (${s("importance")})`
        : `agent wake (${s("reason")}) -> sleep ${s("next_sleep_seconds")}s`;
  else if (row.type === "agent_action") headline = `action: ${s("tool")}`;
  else if (row.type === "manual_instruction") headline = "instruction added";
  else if (row.type === "final_output") headline = "final output";

  return (
    <li
      className={
        "rounded border border-l-4 border-neutral-200 p-2 text-xs dark:border-neutral-800 " +
        (TYPE_STYLE[row.type] ?? "border-l-neutral-300")
      }
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-medium">{headline}</span>
        <span className="shrink-0 text-neutral-500" title={fmtTime(row.created_at)}>
          {fromNow(row.created_at)}
        </span>
      </div>
      {Boolean(p.message || p.reasoning || p.reason) && (
        <p className="mt-1 whitespace-pre-wrap text-neutral-600 dark:text-neutral-400">
          {(p.message as string) || (p.reasoning as string) || (p.reason as string)}
        </p>
      )}
      <details className="mt-1">
        <summary className="cursor-pointer text-neutral-500">payload</summary>
        <pre className="mt-1 overflow-x-auto rounded bg-neutral-100 p-2 dark:bg-neutral-900">
          {JSON.stringify(row.payload, null, 2)}
        </pre>
      </details>
    </li>
  );
}

function FinalOutput({ payload }: { payload: Record<string, unknown> }) {
  const arr = (k: string) => (Array.isArray(payload[k]) ? (payload[k] as string[]) : []);
  return (
    <div className="space-y-2 rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
      <p>{(payload.summary as string) || "(no summary)"}</p>
      {(["important_actions", "key_learnings", "feedback"] as const).map((k) =>
        arr(k).length ? (
          <div key={k}>
            <div className="text-xs uppercase tracking-wide text-neutral-500">{k.replace("_", " ")}</div>
            <ul className="list-inside list-disc text-neutral-600 dark:text-neutral-400">
              {arr(k).map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Control cards
// --------------------------------------------------------------------------- //
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2 rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <h3 className="text-sm font-medium">{title}</h3>
      {children}
    </div>
  );
}

function Note({ msg }: { msg: { kind: "ok" | "err"; text: string } | null }) {
  if (!msg) return null;
  return (
    <p className={msg.kind === "ok" ? "text-xs text-emerald-600" : "text-xs text-red-600"}>
      {msg.text}
    </p>
  );
}

function InjectEventCard({
  runId,
  disabled,
  onDone,
}: {
  runId: string;
  disabled: boolean;
  onDone: () => void;
}) {
  const [type, setType] = useState<string>(EVENT_TYPES[2]); // payment_failed
  const [custom, setCustom] = useState("");
  const [payloadRaw, setPayloadRaw] = useState('{\n  "reason": "card_declined"\n}');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    const eventType = type === "__custom__" ? custom.trim() : type;
    if (!eventType) {
      setMsg({ kind: "err", text: "enter a custom event type" });
      return;
    }
    let payload: Record<string, unknown> = {};
    try {
      payload = payloadRaw.trim() ? JSON.parse(payloadRaw) : {};
    } catch {
      setMsg({ kind: "err", text: "payload is not valid JSON" });
      return;
    }
    setBusy(true);
    try {
      await injectEvent(runId, { type: eventType, payload });
      setMsg({ kind: "ok", text: `sent ${eventType}` });
      onDone();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? `${err.status}: ${err.message}` : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Inject event">
      <form onSubmit={submit} className="space-y-2">
        <select
          className={inputCls}
          value={type}
          onChange={(e) => setType(e.target.value)}
          disabled={disabled}
        >
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
          <option value="__custom__">custom...</option>
        </select>
        {type === "__custom__" && (
          <input
            className={inputCls}
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            placeholder="warehouse_fire"
            disabled={disabled}
          />
        )}
        <textarea
          className={inputCls + " h-20 font-mono text-xs"}
          value={payloadRaw}
          onChange={(e) => setPayloadRaw(e.target.value)}
          disabled={disabled}
        />
        <Button type="submit" disabled={disabled || busy}>
          {busy ? "sending..." : "Send event"}
        </Button>
        <Note msg={msg} />
      </form>
    </Card>
  );
}

function InstructionCard({
  runId,
  disabled,
  onDone,
}: {
  runId: string;
  disabled: boolean;
  onDone: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    setBusy(true);
    try {
      await addInstruction(runId, text.trim());
      setMsg({ kind: "ok", text: "instruction sent" });
      setText("");
      onDone();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? `${err.status}: ${err.message}` : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Add instruction">
      <form onSubmit={submit} className="space-y-2">
        <Field label="">
          <textarea
            className={inputCls + " h-20 text-xs"}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="offer a 10% goodwill credit"
            disabled={disabled}
            required
          />
        </Field>
        <Button type="submit" disabled={disabled || busy || !text.trim()}>
          {busy ? "sending..." : "Send instruction"}
        </Button>
        <Note msg={msg} />
      </form>
    </Card>
  );
}

function InterruptCard({
  runId,
  disabled,
  onDone,
}: {
  runId: string;
  disabled: boolean;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function go() {
    if (!confirm("Interrupt this run? The workflow will produce a final report and exit.")) return;
    setBusy(true);
    setMsg(null);
    try {
      await interruptRun(runId);
      setMsg({ kind: "ok", text: "interrupt sent" });
      onDone();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? `${err.status}: ${err.message}` : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Interrupt (manual termination)">
      <Button
        type="button"
        onClick={go}
        disabled={disabled || busy}
        className="border-amber-400 text-amber-800 hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-amber-950"
      >
        {busy ? "..." : "Interrupt run"}
      </Button>
      <Note msg={msg} />
    </Card>
  );
}
