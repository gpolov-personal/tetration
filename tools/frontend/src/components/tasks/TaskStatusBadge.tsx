const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-green-900/50 text-green-400 border-green-700',
  running: 'bg-blue-900/50 text-blue-400 border-blue-700 animate-pulse',
  failed: 'bg-red-900/50 text-red-400 border-red-700',
  pending: 'bg-yellow-900/50 text-yellow-400 border-yellow-700',
};

export function TaskStatusBadge({ status }: { status?: string }) {
  const s = status ?? 'pending';
  const style = STATUS_STYLES[s] ?? STATUS_STYLES.pending;
  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded border ${style}`}>
      {s}
    </span>
  );
}
