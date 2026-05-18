'use client';

import { useState } from 'react';

export interface SessionControlProps {
  userId: string;
  onSessionCreated?: () => void;
}

export default function SessionControl({ userId, onSessionCreated }: SessionControlProps) {
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const handleStartSession = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/sessions/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_type: 'meeting', end_user_id: userId })
      });
      const data = await response.json();
      setSessionId(data.session_id);
      onSessionCreated?.();
    } catch (error) {
      console.error('Failed to start session:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
      <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Session Control</h3>
      {!sessionId ? (
        <button
          onClick={handleStartSession}
          disabled={loading}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white rounded font-medium transition-colors"
        >
          {loading ? 'Starting...' : 'Start Session'}
        </button>
      ) : (
        <div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mb-2">Session ID</p>
          <p className="font-mono text-xs text-slate-700 dark:text-slate-300 break-all">{sessionId}</p>
        </div>
      )}
    </div>
  );
}
