import type { TaskResponse } from '../api/types';

export interface PipelineFlow {
  id: string;
  label: string;
  startedAt: string;
  boundaryTaskId: number;
  tasks: TaskResponse[];
}

export interface ProjectGroup {
  projectRoot: string;
  flows: PipelineFlow[];
  ungrouped: TaskResponse[];
}

const WORKTREE_SEGMENT = '/.claude/worktrees/';

export function deriveProjectRoot(workingDir: string): string {
  const idx = workingDir.indexOf(WORKTREE_SEGMENT);
  if (idx !== -1) return workingDir.slice(0, idx);
  return workingDir.replace(/\/+$/, '');
}

function isFlowBoundary(task: TaskResponse): boolean {
  return /^eigen:\s*time_split\s*\((?!iteration)/i.test(task.name);
}

function extractFlowLabel(task: TaskResponse): string {
  const match = task.name.match(/\(([^)]+)\)/);
  return match ? match[1] : 'Pipeline run';
}

export function groupByProject(tasks: TaskResponse[]): ProjectGroup[] {
  const byProject = new Map<string, TaskResponse[]>();
  for (const task of tasks) {
    const root = deriveProjectRoot(task.working_dir);
    const list = byProject.get(root) ?? [];
    list.push(task);
    byProject.set(root, list);
  }

  const projects: ProjectGroup[] = [];
  for (const [projectRoot, projectTasks] of byProject) {
    const sorted = [...projectTasks].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );

    const flows: PipelineFlow[] = [];
    const ungrouped: TaskResponse[] = [];
    let currentFlow: PipelineFlow | null = null;

    for (const task of sorted) {
      if (isFlowBoundary(task)) {
        currentFlow = {
          id: `flow-${task.created_at}`,
          label: extractFlowLabel(task),
          startedAt: task.created_at,
          boundaryTaskId: task.id,
          tasks: [task],
        };
        flows.push(currentFlow);
      } else if (currentFlow) {
        currentFlow.tasks.push(task);
      } else {
        ungrouped.push(task);
      }
    }

    flows.sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime());
    projects.push({ projectRoot, flows, ungrouped });
  }

  projects.sort((a, b) => {
    const aLatest = mostRecentTask(a);
    const bLatest = mostRecentTask(b);
    return new Date(bLatest).getTime() - new Date(aLatest).getTime();
  });

  return projects;
}

function mostRecentTask(project: ProjectGroup): string {
  const all = [...project.flows.flatMap((f) => f.tasks), ...project.ungrouped];
  if (all.length === 0) return '1970-01-01T00:00:00Z';
  return all.reduce(
    (latest, t) =>
      new Date(t.created_at).getTime() > new Date(latest).getTime() ? t.created_at : latest,
    all[0].created_at,
  );
}
