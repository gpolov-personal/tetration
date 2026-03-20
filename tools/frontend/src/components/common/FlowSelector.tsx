import type { PipelineFlow, ProjectGroup } from '../../lib/flows';
import { truncatePath, formatDate } from '../../lib/formatters';

interface Props {
  projects: ProjectGroup[];
  currentProject: ProjectGroup | null;
  currentFlow: PipelineFlow | null;
  onSelectProject: (root: string | null) => void;
  onSelectFlow: (flowId: string | null) => void;
}

export function FlowSelector({
  projects,
  currentProject,
  currentFlow,
  onSelectProject,
  onSelectFlow,
}: Props) {
  if (projects.length === 0) {
    return <div className="text-sm text-gray-500">No tasks found.</div>;
  }

  const allTaskCount = projects.reduce(
    (sum, p) => sum + p.flows.reduce((s, f) => s + f.tasks.length, 0) + p.ungrouped.length,
    0,
  );

  return (
    <div className="flex items-center gap-4 flex-wrap">
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-500 whitespace-nowrap">Project:</label>
        <select
          value={currentProject?.projectRoot ?? '__all__'}
          onChange={(e) => onSelectProject(e.target.value === '__all__' ? null : e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500 max-w-[300px]"
          title={currentProject?.projectRoot ?? 'All projects'}
        >
          <option value="__all__">All projects ({allTaskCount} tasks)</option>
          {projects.map((p) => {
            const count = p.flows.reduce((s, f) => s + f.tasks.length, 0) + p.ungrouped.length;
            return (
              <option key={p.projectRoot} value={p.projectRoot}>
                {truncatePath(p.projectRoot, 45)} ({count})
              </option>
            );
          })}
        </select>
      </div>

      {currentProject && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500 whitespace-nowrap">Flow:</label>
          <select
            value={currentFlow?.id ?? '__all__'}
            onChange={(e) => onSelectFlow(e.target.value === '__all__' ? null : e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500 max-w-[350px]"
          >
            <option value="__all__">
              All tasks ({currentProject.flows.reduce((s, f) => s + f.tasks.length, 0) + currentProject.ungrouped.length})
            </option>
            {currentProject.flows.map((f) => (
              <option key={f.id} value={f.id}>
                {f.label} - {formatDate(f.startedAt)} ({f.tasks.length} tasks)
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
