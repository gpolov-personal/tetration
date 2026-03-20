export interface PipelineStage {
  id: string;
  label: string;
  hasDeepen: boolean;
}

export const PIPELINE_STAGES: PipelineStage[] = [
  { id: 'time_split', label: 'Time Split', hasDeepen: true },
  { id: 'bootstrap', label: 'Bootstrap', hasDeepen: true },
  { id: 'space_split', label: 'Space Split', hasDeepen: true },
  { id: 'plan_phase_epic', label: 'Plan Epic', hasDeepen: true },
  { id: 'create_issues_from_plan_swarm', label: 'Create Issues', hasDeepen: false },
  { id: 'orchestrate_swarm', label: 'Orchestrate', hasDeepen: false },
  { id: 'review_swarm_pr', label: 'Review PR', hasDeepen: false },
];

export const PIPELINE_COMMANDS = [
  'eigen_start',
  'time_split',
  'deepen_time_split',
  'bootstrap',
  'deepen_bootstrap',
  'space_split',
  'deepen_space_split',
  'plan_phase_epic',
  'deepen_plan_phase_epic',
  'create_issues_from_plan_swarm',
  'orchestrate_swarm',
  'review_swarm_pr',
  'eigen_continue',
] as const;

export type PipelineCommand = (typeof PIPELINE_COMMANDS)[number];

/**
 * Parse the pipeline stage from a task name.
 * Tasks are named "eigen: time_split (context)" or "eigen: deepen_time_split (context)".
 */
export function parseStageFromTaskName(name: string): string | null {
  const match = name.match(/^eigen:\s*(?:deepen_)?(.+?)(?:\s*\(.*\))?$/);
  if (!match) return null;
  const parsed = match[1].trim();
  const stage = PIPELINE_STAGES.find((s) => s.id === parsed);
  return stage ? stage.id : null;
}

/** Check if a task name corresponds to a deepen command */
export function isDeepenTask(name: string): boolean {
  return /^eigen:\s*deepen_/.test(name);
}

/** Extract the raw command name from a task name */
export function parseCommandFromTaskName(name: string): string | null {
  const match = name.match(/^eigen:\s*(.+?)(?:\s*\(.*\))?$/);
  return match ? match[1].trim() : null;
}

/** Build the Skill invocation prompt for a given command */
export function buildPrompt(command: string): string {
  return `Use the Skill tool to invoke Skill("eigen-squared:${command}"). Follow all its instructions completely.`;
}
