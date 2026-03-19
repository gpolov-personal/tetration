import { useMemo, useState } from 'react';
import { useTasks } from './useTasks';
import { groupByProject } from '../lib/flows';
import type { PipelineFlow, ProjectGroup } from '../lib/flows';
import type { TaskResponse } from '../api/types';

export function useFlows() {
  const { tasks, total, error, loading, refresh } = useTasks();
  const [selectedProjectRoot, setSelectedProjectRoot] = useState<string | null>(null);
  const [selectedFlowId, setSelectedFlowId] = useState<string | null>(null);

  const projects = useMemo(() => groupByProject(tasks), [tasks]);

  // null = "All projects"
  const currentProject: ProjectGroup | null = useMemo(() => {
    if (selectedProjectRoot === null) return null;
    if (projects.length === 0) return null;
    return projects.find((p) => p.projectRoot === selectedProjectRoot) ?? null;
  }, [projects, selectedProjectRoot]);

  const currentFlow: PipelineFlow | null = useMemo(() => {
    if (!currentProject || currentProject.flows.length === 0) return null;
    if (selectedFlowId === null) return null;
    return currentProject.flows.find((f) => f.id === selectedFlowId) ?? null;
  }, [currentProject, selectedFlowId]);

  const flowTasks: TaskResponse[] = useMemo(() => {
    // All projects
    if (currentProject === null) return tasks;
    // Specific project, specific flow
    if (currentFlow) return currentFlow.tasks;
    // Specific project, all tasks (no flow selected or no flows exist)
    return [...currentProject.flows.flatMap((f) => f.tasks), ...currentProject.ungrouped];
  }, [currentProject, currentFlow, tasks]);

  function selectProject(root: string | null) {
    setSelectedProjectRoot(root);
    setSelectedFlowId(null);
  }

  function selectFlow(flowId: string | null) {
    setSelectedFlowId(flowId);
  }

  return {
    projects,
    currentProject,
    currentFlow,
    flowTasks,
    selectProject,
    selectFlow,
    allTasks: tasks,
    total,
    error,
    loading,
    refresh,
  };
}
