import { useParams } from 'react-router-dom';
import { useTaskDetail } from '../hooks/useTaskDetail';
import { TaskDetail } from '../components/tasks/TaskDetail';
import { TaskOutputViewer } from '../components/tasks/TaskOutputViewer';

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const taskId = id ? parseInt(id, 10) : null;
  const { task, latestRun } = useTaskDetail(taskId);

  if (task.loading && !task.data) {
    return <div className="text-gray-500 p-4">Loading task...</div>;
  }

  if (task.error && !task.data) {
    return <div className="text-red-400 p-4">Error loading task: {task.error.message}</div>;
  }

  if (!task.data) {
    return <div className="text-gray-500 p-4">Task not found.</div>;
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-[calc(100vh-8rem)]">
      <div className="lg:w-1/3 overflow-y-auto">
        <TaskDetail task={task.data} onRefresh={() => { task.refresh(); latestRun.refresh(); }} />
      </div>
      <div className="lg:w-2/3 border border-gray-800 rounded-lg overflow-hidden flex flex-col">
        <TaskOutputViewer
          run={latestRun.data}
          loading={latestRun.loading}
          error={latestRun.error}
        />
      </div>
    </div>
  );
}
