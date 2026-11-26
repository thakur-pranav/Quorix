export default function Loading() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading overview">
      <div className="h-16 w-80 animate-pulse rounded-card bg-surface-2" />
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-card bg-surface-2" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_3fr]">
        <div className="h-72 animate-pulse rounded-card bg-surface-2" />
        <div className="h-72 animate-pulse rounded-card bg-surface-2" />
      </div>
    </div>
  );
}
