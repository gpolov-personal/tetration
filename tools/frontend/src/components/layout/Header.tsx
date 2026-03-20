import { Link } from 'react-router-dom';
import { useHealth } from '../../hooks/useHealth';

export function Header() {
  const { healthy, version, loading } = useHealth();

  return (
    <header className="border-b border-gray-800 px-6 py-3 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-3 hover:opacity-80">
        <span className="text-lg font-bold text-gray-100">Eigen Pipeline</span>
      </Link>
      <div className="flex items-center gap-3 text-sm text-gray-400">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              loading ? 'bg-yellow-400' : healthy ? 'bg-green-400' : 'bg-red-400'
            }`}
          />
          <span>{loading ? 'Connecting...' : healthy ? 'Connected' : 'Disconnected'}</span>
        </div>
        {version && <span className="text-gray-600">v{version}</span>}
      </div>
    </header>
  );
}
