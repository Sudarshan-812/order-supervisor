"use client";

import { useState } from "react";
import {
  ApiError,
  BUSINESS_ACTIONS,
  WAKE_AGGRESSIVENESS,
  createSupervisor,
  listSupervisors,
} from "@/lib/api";
import { Button, Field, fmtTime, inputCls, usePoll } from "@/components/ui";

export default function SupervisorsPage() {
  const { data: supervisors, error, refresh } = usePoll(() => listSupervisors(), 5000);

  return (
    <section className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Supervisor templates</h1>
        <p className="mt-1 text-sm text-neutral-500">
          A reusable config for the agent: its base instruction, which of the 5 actions it may
          use, how long it sleeps by default, and how eagerly it wakes. Every run picks one.
        </p>
      </div>

      <NewTemplateForm onCreated={refresh} />

      {error && <p className="text-sm text-red-600">Failed to load: {error}</p>}
      <ul className="space-y-3 text-sm">
        {supervisors?.length === 0 && <li className="text-neutral-400">No templates yet.</li>}
        {supervisors?.map((s) => (
          <li key={s.id} className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
            <div className="flex items-baseline justify-between">
              <span className="font-medium">{s.name}</span>
              <span className="font-mono text-xs text-neutral-500">{s.id}</span>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-neutral-600 dark:text-neutral-400">
              {s.base_instruction}
            </p>
            <pre className="mt-2 overflow-x-auto rounded bg-neutral-100 p-2 text-xs dark:bg-neutral-900">
              {JSON.stringify(s.model_settings, null, 2)}
            </pre>
            <p className="mt-1 text-xs text-neutral-500">created {fmtTime(s.created_at)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function NewTemplateForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [baseInstruction, setBaseInstruction] = useState(
    "You supervise a single e-commerce order end to end. Keep the customer informed, chase the right internal team on any exception, and only act when something needs attention.",
  );
  const [actions, setActions] = useState<string[]>([...BUSINESS_ACTIONS]);
  const [wakeMinutes, setWakeMinutes] = useState(60);
  const [aggressiveness, setAggressiveness] =
    useState<(typeof WAKE_AGGRESSIVENESS)[number]>("balanced");
  const [extraRaw, setExtraRaw] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  function toggle(a: string) {
    setActions((cur) => (cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a]));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    let extra: Record<string, unknown> = {};
    try {
      extra = extraRaw.trim() ? JSON.parse(extraRaw) : {};
    } catch {
      setMsg({ kind: "err", text: "extra config is not valid JSON" });
      return;
    }
    setBusy(true);
    try {
      await createSupervisor({
        name,
        base_instruction: baseInstruction,
        // empty selection means "all 5" on the backend
        allowed_actions: actions.length === BUSINESS_ACTIONS.length ? [] : actions,
        default_wake_minutes: wakeMinutes,
        wake_aggressiveness: aggressiveness,
        extra,
      });
      setMsg({ kind: "ok", text: "Template created" });
      setName("");
      onCreated();
    } catch (err) {
      const text = err instanceof ApiError ? `${err.status}: ${err.message}` : String(err);
      setMsg({ kind: "err", text });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="max-w-xl space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800"
    >
      <h2 className="font-medium">New template</h2>

      <Field label="Name">
        <input
          className={inputCls}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Standard order supervisor"
          required
        />
      </Field>

      <Field label="Base instruction">
        <textarea
          className={inputCls + " h-28"}
          value={baseInstruction}
          onChange={(e) => setBaseInstruction(e.target.value)}
          required
        />
      </Field>

      <Field label="Available actions" hint="unchecking all = all 5 allowed">
        <div className="grid gap-1 sm:grid-cols-2">
          {BUSINESS_ACTIONS.map((a) => (
            <label key={a} className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={actions.includes(a)} onChange={() => toggle(a)} />
              <span className="font-mono">{a}</span>
            </label>
          ))}
        </div>
      </Field>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Default wake (minutes)">
          <input
            type="number"
            min={1}
            className={inputCls}
            value={wakeMinutes}
            onChange={(e) => setWakeMinutes(Number(e.target.value) || 60)}
          />
        </Field>
        <Field label="Wake aggressiveness" hint="borderline / unknown events">
          <select
            className={inputCls}
            value={aggressiveness}
            onChange={(e) =>
              setAggressiveness(e.target.value as (typeof WAKE_AGGRESSIVENESS)[number])
            }
          >
            {WAKE_AGGRESSIVENESS.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Extra model config (JSON)" hint="optional: model name, temperature, ...">
        <textarea
          className={inputCls + " h-16 font-mono text-xs"}
          value={extraRaw}
          onChange={(e) => setExtraRaw(e.target.value)}
        />
      </Field>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy || !name}>
          {busy ? "Creating..." : "Create"}
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
