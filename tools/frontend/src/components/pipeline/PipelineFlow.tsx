import type { TaskResponse } from '../../api/types';
import { PIPELINE_STAGES, parseStageFromTaskName } from '../../lib/pipeline';
import { StageNode } from './StageNode';

interface Props {
  tasks: TaskResponse[];
  onStageClick?: (stageId: string) => void;
}

function deriveStageStatus(
  stageId: string,
  tasks: TaskResponse[],
): 'idle' | 'running' | 'completed' | 'failed' {
  const stageTasks = tasks.filter((t) => parseStageFromTaskName(t.name) === stageId);
  if (stageTasks.length === 0) return 'idle';

  if (stageTasks.some((t) => t.last_run_status === 'running')) return 'running';
  if (stageTasks.some((t) => t.last_run_status === 'failed')) return 'failed';
  if (stageTasks.every((t) => t.last_run_status === 'completed')) return 'completed';
  return 'idle';
}

export function PipelineFlow({ tasks, onStageClick }: Props) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto py-4 px-2">
      {PIPELINE_STAGES.map((stage, i) => (
        <div key={stage.id} className="flex items-center gap-2">
          {i > 0 && (
            <svg width="20" height="20" viewBox="0 0 20 20" className="text-gray-600 flex-shrink-0">
              <path d="M4 10 L16 10 M12 6 L16 10 L12 14" stroke="currentColor" fill="none" strokeWidth="1.5" />
            </svg>
          )}
          <StageNode
            stage={stage}
            status={deriveStageStatus(stage.id, tasks)}
            onClick={() => onStageClick?.(stage.id)}
          />
        </div>
      ))}
    </div>
  );
}
