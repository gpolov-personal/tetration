import { PIPELINE_COMMANDS, buildPrompt } from '../../lib/pipeline';
import type { TaskRequest } from '../../api/types';

interface Props {
  onSelect: (preset: Partial<TaskRequest>) => void;
}

export function PipelineQuickLaunch({ onSelect }: Props) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-3">Quick Launch</h3>
      <div className="flex flex-wrap gap-2">
        {PIPELINE_COMMANDS.map((cmd) => (
          <button
            key={cmd}
            onClick={() => {
              const scheduled = new Date(Date.now() + 3 * 60 * 1000).toISOString();
              onSelect({
                name: `eigen: ${cmd}`,
                prompt: buildPrompt(cmd),
                cron_expr: '',
                scheduled_at: scheduled,
                enabled: true,
              });
            }}
            className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded text-gray-300 transition-colors"
          >
            {cmd}
          </button>
        ))}
      </div>
    </div>
  );
}
