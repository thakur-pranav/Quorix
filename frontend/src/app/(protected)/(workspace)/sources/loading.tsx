export default function Loading() {
  return (
    <div className="flex flex-col gap-8" aria-busy="true" aria-label="Loading sources">
      <div className="h-16 w-72 animate-pulse rounded-card bg-surface-2" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-44 animate-pulse rounded-card bg-surface-2" />
        <div className="h-44 animate-pulse rounded-card bg-surface-2" />
      </div>
      <div className="h-28 animate-pulse rounded-card bg-surface-2" />
    </div>
  );
}
