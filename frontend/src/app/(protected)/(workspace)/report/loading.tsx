export default function Loading() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading report">
      <div className="h-16 w-80 animate-pulse rounded-card bg-surface-2" />
      <div className="h-36 animate-pulse rounded-card bg-surface-2" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-40 animate-pulse rounded-card bg-surface-2" />
      ))}
    </div>
  );
}
