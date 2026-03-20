import { useNavigate } from 'react-router-dom';
import type { TaskResponse } from '../../api/types';
import { formatDate } from '../../lib/formatters';
import { parseStageFromTaskName, isDeepenTask } from '../../lib/pipeline';
import { TaskStatusBadge } from './TaskStatusBadge';
import { JsonViewer } from '../common/JsonViewer';
import { api } from '../../api/client';
import { useState } from 'react';

interface Props {
  task: TaskResponse;
  onRefresh: () => void;
}

export function TaskDetail({ task, onRefresh }: Props) {
  const navigate = useNavigate();
  const [actionLoading, setActionLoading] = useState(false);
  const stage = parseStageFromTaskName(task.name);
  const isDeepen = isDeepenTask(task.name);

  async function handleRun() {
    setActionLoading(true);
    try {
      await api.runTask(task.id);
      onRefresh();
    } finally {
      setActionLoading(false);
    }
  }

  async function handleToggle() {
    setActionLoading(true);
    try {
      await api.toggleTask(task.id);
      onRefresh();
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete task "${task.name}"?`)) return;
    await api.deleteTask(task.id);
    navigate('/tasks');
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-lg font-semibold text-gray-100">{task.name}</h2>
        <TaskStatusBadge status={task.last_run_status} />
        {stage && (
          <span className="text-xs px-2 py-0.5 rounded bg-purple-900/50 text-purple-400 border border-purple-700">
            {stage}{isDeepen ? ' (deepen)' : ''}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <Field label="Working Dir" value={task.working_dir} mono />
        <Field label="Enabled" value={task.enabled ? 'Yes' : 'No'} />
        <Field label="Scheduled At" value={task.scheduled_at ? formatDate(task.scheduled_at) : '-'} />
        <Field label="Cron" value={task.cron_expr || '-'} />
        <Field label="Created" value={formatDate(task.created_at)} />
        <Field label="Last Run" value={task.last_run_at ? formatDate(task.last_run_at) : '-'} />
        <Field label="Next Run" value={task.next_run_at ? formatDate(task.next_run_at) : '-'} />
        <Field label="One-off" value={task.is_one_off ? 'Yes' : 'No'} />
      </div>

      <JsonViewer data={{ prompt: task.prompt }} label="Prompt" />

      <div className="flex gap-2 pt-2">
        <button
          onClick={handleRun}
          disabled={actionLoading}
          className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white"
        >
          Run Now
        </button>
        <button
          onClick={handleToggle}
          disabled={actionLoading}
          className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded text-gray-200"
        >
          {task.enabled ? 'Disable' : 'Enable'}
        </button>
        <button
          onClick={handleDelete}
          className="px-3 py-1.5 text-sm bg-red-900/50 hover:bg-red-800 rounded text-red-400"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <span className="text-gray-500 text-xs">{label}</span>
      <div className={`text-gray-300 ${mono ? 'font-mono text-xs break-all' : ''}`}>{value}</div>
    </div>
  );
}
