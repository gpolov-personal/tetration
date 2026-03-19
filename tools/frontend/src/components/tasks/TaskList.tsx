import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { TaskResponse } from '../../api/types';
import { TimeAgo } from '../common/TimeAgo';
import { TaskStatusBadge } from './TaskStatusBadge';
import { truncatePath } from '../../lib/formatters';
import { parseStageFromTaskName } from '../../lib/pipeline';

interface Props {
  tasks: TaskResponse[];
  loading: boolean;
}

export function TaskList({ tasks, loading }: Props) {
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filtered = tasks.filter((t) => {
    if (filter && !t.name.toLowerCase().includes(filter.toLowerCase())) return false;
    if (statusFilter !== 'all' && t.last_run_status !== statusFilter) return false;
    return true;
  });

  return (
    <div>
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Filter by name..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All statuses</option>
          <option value="completed">Completed</option>
          <option value="running">Running</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
        </select>
      </div>

      {loading && tasks.length === 0 ? (
        <div className="text-gray-500 text-center py-8">Loading tasks...</div>
      ) : filtered.length === 0 ? (
        <div className="text-gray-500 text-center py-8">No tasks found.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase text-gray-400 border-b border-gray-700">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Stage</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Working Dir</th>
                <th className="px-4 py-3">Scheduled</th>
                <th className="px-4 py-3">Last Run</th>
                <th className="px-4 py-3">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((task) => (
                <tr
                  key={task.id}
                  className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/tasks/${task.id}`}
                      className="text-blue-400 hover:text-blue-300 hover:underline"
                    >
                      {task.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {parseStageFromTaskName(task.name) ?? '-'}
                  </td>
                  <td className="px-4 py-3">
                    <TaskStatusBadge status={task.last_run_status} />
                  </td>
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs" title={task.working_dir}>
                    {truncatePath(task.working_dir)}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {task.scheduled_at ? <TimeAgo date={task.scheduled_at} /> : task.cron_expr || '-'}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {task.last_run_at ? <TimeAgo date={task.last_run_at} /> : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block w-2 h-2 rounded-full ${task.enabled ? 'bg-green-400' : 'bg-gray-600'}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
