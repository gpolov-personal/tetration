import { useFlows } from '../hooks/useFlows';
import { FlowSelector } from '../components/common/FlowSelector';
import { TaskList } from '../components/tasks/TaskList';

export function TaskListPage() {
  const {
    projects,
    currentProject,
    currentFlow,
    flowTasks,
    selectProject,
    selectFlow,
    total,
    loading,
  } = useFlows();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Tasks</h1>
        <span className="text-sm text-gray-500">{total} total</span>
      </div>

      <FlowSelector
        projects={projects}
        currentProject={currentProject}
        currentFlow={currentFlow}
        onSelectProject={selectProject}
        onSelectFlow={selectFlow}
      />

      <TaskList tasks={flowTasks} loading={loading} />
    </div>
  );
}
