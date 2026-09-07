// Supervisor templates: list existing + form to create one
// (name, base instruction, available actions, default wake behaviour,
//  wake aggressiveness, optional model config). Scaffold.

export default function SupervisorsPage() {
  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold">Supervisor templates</h1>

      {/* TODO: fetch listSupervisors() */}
      <ul className="space-y-2 text-sm text-neutral-400">
        <li>No templates yet - scaffold.</li>
      </ul>

      {/* TODO: form -> createSupervisor() */}
      <form className="max-w-lg space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800">
        <h2 className="font-medium">New template</h2>
        <input className="w-full rounded border px-2 py-1 text-sm" placeholder="name" disabled />
        <textarea className="w-full rounded border px-2 py-1 text-sm" placeholder="base instruction" disabled />
        <p className="text-xs text-neutral-500">
          available_actions, default_wake_minutes, wake_aggressiveness, model_config - TODO
        </p>
        <button className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-neutral-900" disabled>
          Create
        </button>
      </form>
    </section>
  );
}
