"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  EVENT_TYPES,
  addInstruction,
  getRun,
  injectEvent,
  interruptRun,
  listScenarios,
  pauseRun,
  resumeRun,
  simulateRun,
  terminateRun,
  type ActivityLogRow,
  type RunDetail,
} from "@/lib/api";
import { Button, StatusBadge, fmtTime, fromNow, inputCls, usePoll } from "@/components/ui";

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
      <div>
        <div className="flex items-center gap-3">
          <Link href="/" className="text-sm underline">
            &larr; all runs
          </Link>
          <h1 className="text-lg font-semibold">
            Order {run ? run.order_id : runId}
            {run && (
              <span className="ml-2 align-middle">
                <StatusBadge status={run.status} />
              </span>
            )}
            {live?.paused && (
              <span className="ml-2 align-middle rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-300">
                paused
              </span>
            )}
          </h1>
        </div>
        <p className="mt-1 text-xs text-neutral-500">
          One Temporal workflow supervises this order. The page refreshes every 3s while it runs.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">Failed to load run: {error}</p>}

      <div className="grid gap-8 lg:grid-cols-[1.8fr_1fr]">
        {/* left: state + timeline */}
        <div className="space-y-6">
          <StatePanel run={run} live={live} />

          <Section
            title="Memory summary"
            hint="A compact rolling summary the agent rewrites on every wake."
          >
            <pre className="whitespace-pre-wrap rounded bg-neutral-100 p-3 text-xs dark:bg-neutral-900">
              {live?.memory_summary || run?.memory_summary || "(empty so far)"}
            </pre>
          </Section>

          {finalRow && (
            <Section
              title="Final output"
              hint="Produced by the agent as the last step when the workflow ended."
            >
              <FinalOutput payload={finalRow.payload} />
            </Section>
          )}

          <Section
            title={`Timeline (${timeline.length})`}
            hint="Newest first. Each row is one event, wake/sleep decision, action, or instruction. Open 'details' for the raw record."
          >
            <ol className="space-y-2">
              {timeline.length === 0 && (
                <li className="text-sm text-neutral-400">Nothing has happened yet.</li>
              )}
              {[...timeline].reverse().map((a) => (
                <TimelineItem key={a.id} row={a} />
              ))}
            </ol>
          </Section>
        </div>

        {/* right: control panel */}
        <aside className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
              Control panel
            </h2>
            <p className="mt-1 text-xs text-neutral-500">Drive the run: feed it events or instructions, or change its lifecycle.</p>
          </div>
          {done && (
            <p className="rounded bg-neutral-100 p-2 text-xs text-neutral-500 dark:bg-neutral-900">
              This run is {run?.status}. The workflow has ended, so these controls are disabled.
            </p>
          )}
          <ScenarioCard runId={runId} disabled={done} onDone={refresh} />
          <InjectEventCard runId={runId} disabled={done} onDone={refresh} />
          <InstructionCard runId={runId} disabled={done} onDone={refresh} />
          <LifecycleCard
            runId={runId}
            disabled={done}
            paused={Boolean(live?.paused)}
            onDone={refresh}
          />
        </aside>
      </div>
    </section>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">{title}</h2>
      {hint && <p className="mb-2 mt-0.5 text-xs text-neutral-500">{hint}</p>}
      {children}
    </div>
  );
}

function StatePanel({
  run,
  live,
}: {
  run: RunDetail["run"] | undefined;
  live: RunDetail["live"];
}) {
  const yn = (b: boolean | undefined) => (b === undefined ? "?" : b ? "yes" : "no");
  return (
    <div className="space-y-4 rounded border border-neutral-200 p-4 dark:border-neutral-800">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Run record
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <Meta label="status" value={run?.status ?? "-"} />
          <Meta
            label="next scheduled wake"
            value={
              run?.next_wake_at
                ? `${fromNow(run.next_wake_at)} (${fmtTime(run.next_wake_at)})`
                : "not scheduled yet"
            }
          />
          <Meta label="last updated" value={run ? fromNow(run.updated_at) : "-"} />
          <Meta label="workflow id" value={run?.workflow_id ?? "-"} mono className="col-span-full" />
        </div>
      </div>

      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Live agent state
          <span className="ml-2 font-normal normal-case text-neutral-400">
            queried from the running workflow
          </span>
        </div>
        {live ? (
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            <Meta label="agent wakes so far" value={String(live.processed_wakes)} />
            <Meta label="events waiting in queue" value={String(live.queued_events)} />
            <Meta label="paused" value={yn(live.paused)} />
            {live.standing_instructions.length > 0 && (
              <Meta
                label="standing instructions"
                value={live.standing_instructions.join("  •  ")}
                className="col-span-full"
              />
            )}
            {live.wakeup_guidance && (
              <Meta
                label="wake-up guidance the agent wrote for the classifier"
                value={live.wakeup_guidance}
                className="col-span-full"
              />
            )}
            {live.last_reasoning && (
              <Meta
                label="agent's reasoning at its last wake"
                value={live.last_reasoning}
                className="col-span-full"
              />
            )}
          </div>
        ) : (
          <p className="text-sm text-neutral-400">
            Unavailable (the workflow has ended, or the worker is down).
          </p>
        )}
      </div>
    </div>
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

// Timeline rendering.
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
  if (row.type === "incoming_event") headline = `event received: ${s("type")}`;
  else if (row.type === "wake_decision")
    headline =
      p.stage === "classifier"
        ? `classifier decided: ${p.wake_now ? "wake the agent now" : "stay asleep"} (${s("importance")})`
        : `agent woke (${s("reason")}), then slept ${s("next_sleep_seconds")}s`;
  else if (row.type === "agent_action") headline = `agent action: ${s("tool")}`;
  else if (row.type === "manual_instruction") headline = "instruction added";
  else if (row.type === "final_output") headline = "final output produced";

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
        <summary className="cursor-pointer text-neutral-500">details</summary>
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
            <div className="text-xs uppercase tracking-wide text-neutral-500">
              {k.replace("_", " ")}
            </div>
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

// Control-panel cards.
function Card({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2 rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <div>
        <h3 className="text-sm font-medium">{title}</h3>
        {hint && <p className="text-xs text-neutral-500">{hint}</p>}
      </div>
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
    <Card
      title="Inject one event"
      hint="Delivered as a signal. The classifier then decides whether it wakes the agent."
    >
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
          <option value="__custom__">custom (unknown type)...</option>
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
          aria-label="event payload JSON"
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
    <Card
      title="Add an instruction"
      hint="Becomes a standing instruction in this run's context and wakes the agent."
    >
      <form onSubmit={submit} className="space-y-2">
        <textarea
          className={inputCls + " h-20 text-xs"}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. if shipment is delayed, escalate to logistics and offer a credit"
          disabled={disabled}
          required
          aria-label="instruction text"
        />
        <Button type="submit" disabled={disabled || busy || !text.trim()}>
          {busy ? "sending..." : "Send instruction"}
        </Button>
        <Note msg={msg} />
      </form>
    </Card>
  );
}

function LifecycleCard({
  runId,
  disabled,
  paused,
  onDone,
}: {
  runId: string;
  disabled: boolean;
  paused: boolean;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function act(label: string, fn: () => Promise<unknown>, confirmText?: string) {
    if (confirmText && !confirm(confirmText)) return;
    setBusy(label);
    setMsg(null);
    try {
      await fn();
      setMsg({ kind: "ok", text: `${label} sent` });
      onDone();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? `${err.status}: ${err.message}` : String(err) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title="Lifecycle">
      <div className="flex flex-wrap gap-2">
        {paused ? (
          <Button type="button" disabled={disabled || !!busy} onClick={() => act("resume", () => resumeRun(runId))}>
            {busy === "resume" ? "..." : "Resume"}
          </Button>
        ) : (
          <Button type="button" disabled={disabled || !!busy} onClick={() => act("pause", () => pauseRun(runId))}>
            {busy === "pause" ? "..." : "Pause"}
          </Button>
        )}
        <Button
          type="button"
          disabled={disabled || !!busy}
          onClick={() => act("interrupt", () => interruptRun(runId))}
        >
          {busy === "interrupt" ? "..." : "Interrupt"}
        </Button>
        <Button
          type="button"
          disabled={disabled || !!busy}
          onClick={() =>
            act(
              "terminate",
              () => terminateRun(runId),
              "Terminate this run? The workflow will produce a final report and exit.",
            )
          }
          className="border-amber-400 text-amber-800 hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-amber-950"
        >
          {busy === "terminate" ? "..." : "Terminate"}
        </Button>
      </div>
      <ul className="mt-1 space-y-0.5 text-xs text-neutral-500">
        <li><b>Pause</b> stops agent inference; events still queue.</li>
        <li><b>Interrupt</b> wakes the agent now to re-check. The run keeps going.</li>
        <li><b>Terminate</b> ends the run now and writes a final report.</li>
      </ul>
      <Note msg={msg} />
    </Card>
  );
}

function ScenarioCard({
  runId,
  disabled,
  onDone,
}: {
  runId: string;
  disabled: boolean;
  onDone: () => void;
}) {
  const [scenarios, setScenarios] = useState<Record<string, string[]>>({});
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    listScenarios()
      .then((s) => {
        setScenarios(s);
        setName(Object.keys(s)[0] ?? "");
      })
      .catch(() => setScenarios({}));
  }, []);

  async function run() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await simulateRun(runId, name);
      setMsg({ kind: "ok", text: `playing: ${r.events.join(", ")}` });
      onDone();
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof ApiError ? `${err.status}: ${err.message}` : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Event generator"
      hint="Replays a canned sequence of order events into this run, a couple of seconds apart."
    >
      <select
        className={inputCls}
        value={name}
        onChange={(e) => setName(e.target.value)}
        disabled={disabled}
      >
        {Object.keys(scenarios).length === 0 && <option value="">(no scenarios)</option>}
        {Object.entries(scenarios).map(([k, evs]) => (
          <option key={k} value={k}>
            {k} ({evs.length} events)
          </option>
        ))}
      </select>
      {name && scenarios[name] && (
        <p className="text-xs text-neutral-500">{scenarios[name].join(", ")}</p>
      )}
      <Button type="button" onClick={run} disabled={disabled || busy || !name}>
        {busy ? "starting..." : "Run scenario"}
      </Button>
      <Note msg={msg} />
    </Card>
  );
}
