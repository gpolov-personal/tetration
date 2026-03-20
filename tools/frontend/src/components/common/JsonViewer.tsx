import { useState } from 'react';

export function JsonViewer({ data, label }: { data: unknown; label?: string }) {
  const [open, setOpen] = useState(false);
  const text = JSON.stringify(data, null, 2);

  return (
    <div className="border border-gray-700 rounded">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-3 py-2 text-sm text-gray-400 hover:bg-gray-800 flex items-center gap-2"
      >
        <span className={`transition-transform ${open ? 'rotate-90' : ''}`}>&#9654;</span>
        {label ?? 'JSON'}
      </button>
      {open && (
        <pre className="px-3 pb-3 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
          {text}
        </pre>
      )}
    </div>
  );
}
