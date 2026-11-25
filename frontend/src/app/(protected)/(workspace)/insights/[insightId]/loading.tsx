export default function Loading() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading topic">
      <div className="h-20 w-96 max-w-full animate-pulse rounded-card bg-surface-2" />
      <div className="h-20 animate-pulse rounded-card bg-surface-2" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-56 animate-pulse rounded-card bg-surface-2" />
        <div className="h-56 animate-pulse rounded-card bg-surface-2" />
      </div>
    </div>
  );
}
