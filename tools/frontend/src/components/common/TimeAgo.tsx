import { useEffect, useState } from 'react';
import { timeAgo } from '../../lib/formatters';

export function TimeAgo({ date }: { date: string }) {
  const [text, setText] = useState(() => timeAgo(date));

  useEffect(() => {
    setText(timeAgo(date));
    const id = setInterval(() => setText(timeAgo(date)), 10000);
    return () => clearInterval(id);
  }, [date]);

  return <span title={new Date(date).toLocaleString()}>{text}</span>;
}
