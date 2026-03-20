import { CreateTaskForm } from '../components/forms/CreateTaskForm';

export function CreateTaskPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-100">Create Task</h1>
      <CreateTaskForm />
    </div>
  );
}
