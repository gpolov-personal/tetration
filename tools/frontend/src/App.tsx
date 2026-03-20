import { Routes, Route } from 'react-router-dom';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { TaskListPage } from './pages/TaskListPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { CreateTaskPage } from './pages/CreateTaskPage';

export default function App() {
  return (
    <div className="flex flex-col h-screen">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/tasks" element={<TaskListPage />} />
            <Route path="/tasks/new" element={<CreateTaskPage />} />
            <Route path="/tasks/:id" element={<TaskDetailPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
