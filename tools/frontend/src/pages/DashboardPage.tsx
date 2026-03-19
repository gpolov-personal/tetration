import { useNavigate, Link } from 'react-router-dom';
import { useFlows } from '../hooks/useFlows';
import { PipelineFlow } from '../components/pipeline/PipelineFlow';
import { FlowSelector } from '../components/common/FlowSelector';
import { TaskStatusBadge } from '../components/tasks/TaskStatusBadge';
import { TimeAgo } from '../components/common/TimeAgo';

export function DashboardPage() {
  const {
    projects,
    currentProject,
    currentFlow,
    flowTasks,
    selectProject,
    selectFlow,
    loading,
  } = useFlows();
  const navigate = useNavigate();

  const recentTasks = [...flowTasks]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 10);

  const runningCount = flowTasks.filter((t) => t.last_run_status === 'running').length;
  const completedCount = flowTasks.filter((t) => t.last_run_status === 'completed').length;
  const failedCount = flowTasks.filter((t) => t.last_run_status === 'failed').length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-100">Pipeline Dashboard</h1>

      <FlowSelector
        projects={projects}
        currentProject={currentProject}
        currentFlow={currentFlow}
        onSelectProject={selectProject}
        onSelectFlow={selectFlow}
      />

      <div className="flex gap-4 text-sm">
        <Stat label="Total" value={flowTasks.length} />
        <Stat label="Running" value={runningCount} color="text-blue-400" />
        <Stat label="Completed" value={completedCount} color="text-green-400" />
        <Stat label="Failed" value={failedCount} color="text-red-400" />
      </div>

      <div className="border border-gray-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-gray-400 mb-2">Pipeline Flow</h2>
        <PipelineFlow
          tasks={flowTasks}
          onStageClick={(stageId) => navigate(`/tasks?stage=${stageId}`)}
        />
      </div>

      <div className="border border-gray-800 rounded-lg">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-400">
            Recent Tasks{currentFlow ? ` - ${currentFlow.label}` : ''}
          </h2>
          <Link to="/tasks" className="text-xs text-blue-400 hover:text-blue-300">View all</Link>
        </div>
        {loading && recentTasks.length === 0 ? (
          <div className="text-gray-500 text-center py-8">Loading...</div>
        ) : recentTasks.length === 0 ? (
          <div className="text-gray-500 text-center py-8">No tasks in this flow.</div>
        ) : (
          <table className="w-full text-sm text-left">
            <tbody>
              {recentTasks.map((task) => (
                <tr key={task.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-2">
                    <Link to={`/tasks/${task.id}`} className="text-blue-400 hover:text-blue-300">
                      {task.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <TaskStatusBadge status={task.last_run_status} />
                  </td>
                  <td className="px-4 py-2 text-gray-400 text-xs">
                    <TimeAgo date={task.updated_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg px-4 py-2">
      <div className={`text-xl font-bold ${color ?? 'text-gray-200'}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
