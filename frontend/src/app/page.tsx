// Runs dashboard: list active + completed runs, start a new run.
// Scaffold - renders static placeholders; wire to lib/api.ts next.

export default function RunsPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Runs</h1>
        {/* TODO: <NewRunDialog /> -> createRun() */}
        <button className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-neutral-900">
          Start run
        </button>
      </div>

      {/* TODO: fetch listRuns(); poll every few seconds for live status */}
      <table className="w-full text-left text-sm">
        <thead className="text-neutral-500">
          <tr>
            <th className="py-2">Order</th>
            <th>Status</th>
            <th>Sleep</th>
            <th>Next wake</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-neutral-200 dark:border-neutral-800">
            <td className="py-2 text-neutral-400" colSpan={5}>
              No runs yet - scaffold.
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
