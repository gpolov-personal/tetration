import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import type { TaskRequest } from '../../api/types';
import { PipelineQuickLaunch } from './PipelineQuickLaunch';

const EMPTY_FORM: TaskRequest = {
  name: '',
  prompt: '',
  cron_expr: '',
  scheduled_at: '',
  working_dir: '',
  discord_webhook: '',
  slack_webhook: '',
  enabled: true,
};

export function CreateTaskForm() {
  const navigate = useNavigate();
  const [form, setForm] = useState<TaskRequest>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof TaskRequest>(key: K, value: TaskRequest[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handlePreset(preset: Partial<TaskRequest>) {
    setForm((prev) => ({ ...prev, ...preset }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const task = await api.createTask({
        ...form,
        scheduled_at: form.scheduled_at || undefined,
        discord_webhook: form.discord_webhook || undefined,
        slack_webhook: form.slack_webhook || undefined,
      });
      navigate(`/tasks/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PipelineQuickLaunch onSelect={handlePreset} />

      <hr className="border-gray-800" />

      <form onSubmit={handleSubmit} className="space-y-4">
        <InputField label="Name" value={form.name} onChange={(v) => set('name', v)} required />
        <div>
          <label className="block text-sm text-gray-400 mb-1">Prompt</label>
          <textarea
            value={form.prompt}
            onChange={(e) => set('prompt', e.target.value)}
            required
            rows={4}
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-blue-500"
          />
        </div>
        <InputField label="Working Dir" value={form.working_dir} onChange={(v) => set('working_dir', v)} required mono />
        <div className="grid grid-cols-2 gap-4">
          <InputField label="Scheduled At (ISO 8601)" value={form.scheduled_at ?? ''} onChange={(v) => set('scheduled_at', v)} />
          <InputField label="Cron Expression" value={form.cron_expr} onChange={(v) => set('cron_expr', v)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <InputField label="Discord Webhook" value={form.discord_webhook ?? ''} onChange={(v) => set('discord_webhook', v)} />
          <InputField label="Slack Webhook" value={form.slack_webhook ?? ''} onChange={(v) => set('slack_webhook', v)} />
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => set('enabled', e.target.checked)}
            className="rounded"
          />
          <label className="text-sm text-gray-400">Enabled</label>
        </div>

        {error && <div className="text-red-400 text-sm">{error}</div>}

        <button
          type="submit"
          disabled={submitting}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white text-sm"
        >
          {submitting ? 'Creating...' : 'Create Task'}
        </button>
      </form>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  required,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className={`w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 ${mono ? 'font-mono' : ''}`}
      />
    </div>
  );
}
