import type { PipelineStage } from '../../lib/pipeline';

interface Props {
  stage: PipelineStage;
  status: 'idle' | 'running' | 'completed' | 'failed';
  onClick?: () => void;
}

const STATUS_RING: Record<string, string> = {
  idle: 'border-gray-700',
  running: 'border-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]',
  completed: 'border-green-600',
  failed: 'border-red-600',
};

const STATUS_BG: Record<string, string> = {
  idle: 'bg-gray-800/50',
  running: 'bg-blue-900/30',
  completed: 'bg-green-900/20',
  failed: 'bg-red-900/20',
};

export function StageNode({ stage, status, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg border-2 transition-all hover:scale-105 min-w-[100px]
        ${STATUS_RING[status]} ${STATUS_BG[status]}`}
    >
      <span className="text-xs font-medium text-gray-200">{stage.label}</span>
      {stage.hasDeepen && (
        <span className="text-[10px] text-gray-500">+ deepen</span>
      )}
      {status === 'running' && (
        <span className="animate-spin inline-block w-3 h-3 border border-blue-400 border-t-transparent rounded-full" />
      )}
    </button>
  );
}
