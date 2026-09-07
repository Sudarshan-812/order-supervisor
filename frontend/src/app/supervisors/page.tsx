"use client";

import { useState } from "react";
import { ApiError, createSupervisor, listSupervisors } from "@/lib/api";
import { Button, Field, fmtTime, inputCls, usePoll } from "@/components/ui";

const BUSINESS_ACTIONS_HINT =
  'optional keys: default_wake_minutes (int), allowed_actions (subset of ' +
  "message_fulfillment_team, message_payments_team, message_logistics_team, " +
  "message_customer, create_internal_note; empty = all 5)";

export default function SupervisorsPage() {
  const { data: supervisors, error, refresh } = usePoll(() => listSupervisors(), 5000);

  return (
    <section className="space-y-8">
      <h1 className="text-xl font-semibold">Supervisor templates</h1>

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
              model_settings = {JSON.stringify(s.model_settings, null, 2)}
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
  const [settingsRaw, setSettingsRaw] = useState(
    '{\n  "default_wake_minutes": 60,\n  "allowed_actions": []\n}',
  );
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    let model_settings: Record<string, unknown> = {};
    try {
      model_settings = settingsRaw.trim() ? JSON.parse(settingsRaw) : {};
    } catch {
      setMsg({ kind: "err", text: "model_settings is not valid JSON" });
      return;
    }
    setBusy(true);
    try {
      await createSupervisor({ name, base_instruction: baseInstruction, model_settings });
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

      <Field label="model_settings (JSON)" hint={BUSINESS_ACTIONS_HINT}>
        <textarea
          className={inputCls + " h-28 font-mono text-xs"}
          value={settingsRaw}
          onChange={(e) => setSettingsRaw(e.target.value)}
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
