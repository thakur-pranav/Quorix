export default function Loading() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading chat">
      <div className="h-16 w-80 animate-pulse rounded-card bg-surface-2" />
      <div className="h-[28rem] animate-pulse rounded-card bg-surface-2" />
    </div>
  );
}
