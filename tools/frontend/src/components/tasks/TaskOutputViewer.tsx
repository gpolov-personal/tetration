import { useEffect, useRef } from 'react';
import type { TaskRunResponse } from '../../api/types';
import { elapsedSince } from '../../lib/formatters';
import { TaskStatusBadge } from './TaskStatusBadge';

interface Props {
  run: TaskRunResponse | null;
  loading: boolean;
  error: Error | null;
}

export function TaskOutputViewer({ run, loading, error }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [run?.output]);

  if (loading && !run) {
    return <div className="text-gray-500 p-4">Loading run data...</div>;
  }

  if (error && !run) {
    return <div className="text-gray-500 p-4">No runs yet.</div>;
  }

  if (!run) {
    return <div className="text-gray-500 p-4">No runs yet.</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-700 text-sm">
        <TaskStatusBadge status={run.status} />
        {run.status === 'running' && run.started_at && (
          <span className="text-blue-400">Running for {elapsedSince(run.started_at)}</span>
        )}
        {run.duration_ms != null && (
          <span className="text-gray-400">{(run.duration_ms / 1000).toFixed(1)}s</span>
        )}
        {run.error && <span className="text-red-400 truncate">{run.error}</span>}
      </div>
      <div className="flex-1 overflow-y-auto bg-gray-950 p-4">
        {run.status === 'running' && !run.output ? (
          <div className="flex items-center gap-2 text-blue-400">
            <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" />
            Running... output will appear when complete
          </div>
        ) : (
          <pre className="text-sm font-mono text-gray-300 whitespace-pre-wrap break-words">
            {run.output || '(no output)'}
          </pre>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
