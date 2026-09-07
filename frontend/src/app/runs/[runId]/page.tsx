// Run detail: timeline + activity history, memory summary, current status /
// sleep state / next wake-up, plus controls: inject event, add instruction,
// interrupt / pause / resume / terminate. Scaffold.

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  return (
    <section className="grid gap-8 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Run {runId}</h1>

        {/* TODO: getRun(runId); poll for live updates */}
        <div className="rounded border border-neutral-200 p-4 text-sm dark:border-neutral-800">
          <p className="text-neutral-500">status / sleep_state / next_wake_at - scaffold</p>
        </div>

        <h2 className="font-medium">Timeline</h2>
        <ol className="space-y-2 text-sm text-neutral-400">
          <li>events, wake/sleep decisions, agent actions, instructions - scaffold</li>
        </ol>

        <h2 className="font-medium">Memory summary</h2>
        <pre className="whitespace-pre-wrap rounded bg-neutral-100 p-3 text-xs dark:bg-neutral-900">
          (empty - scaffold)
        </pre>

        <h2 className="font-medium">Final output</h2>
        <p className="text-sm text-neutral-400">summary / actions / learnings / feedback - scaffold</p>
      </div>

      <aside className="space-y-4 text-sm">
        <h2 className="font-medium">Controls</h2>
        {/* TODO: injectEvent / addInstruction / interruptRun / resumeRun / terminateRun */}
        <div className="space-y-2 rounded border border-neutral-200 p-4 dark:border-neutral-800">
          <p className="text-neutral-500">Inject event</p>
          <p className="text-neutral-500">Add instruction</p>
          <p className="text-neutral-500">Interrupt / Resume / Terminate</p>
        </div>
      </aside>
    </section>
  );
}
