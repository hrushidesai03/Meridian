'use client';

import { useState, useEffect } from 'react';
import SessionControl from '@/components/SessionControl';
import CommitmentsTable from '@/components/CommitmentsTable';
import DecisionsTable from '@/components/DecisionsTable';
import DriftAlerts from '@/components/DriftAlerts';
import RetroPanel from '@/components/RetroPanel';
import { fetchCommitments, fetchDecisions, fetchAlerts } from '@/lib/api';

const USER_ID = 'user_001';

export default function Dashboard() {
  const [tab, setTab] = useState<'commitments' | 'decisions' | 'alerts' | 'retro'>('commitments');
  const [commitments, setCommitments] = useState<any[]>([]);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [commData, decData, alertData] = await Promise.all([
        fetchCommitments(USER_ID),
        fetchDecisions(USER_ID),
        fetchAlerts(USER_ID)
      ]);
      setCommitments(commData);
      setDecisions(decData);
      setAlerts(alertData);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800 p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-2">
            Meridian
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            Real-time commitment intelligence and accountability tracking
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-8">
          <SessionControl userId={USER_ID} onSessionCreated={loadData} />
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <div className="text-2xl font-bold text-blue-600">{commitments.length}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400">Active Commitments</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <div className="text-2xl font-bold text-green-600">{decisions.length}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400">Decisions</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
            <div className="text-2xl font-bold text-red-600">{alerts.length}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400">Alerts</div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-lg shadow">
          <div className="border-b border-slate-200 dark:border-slate-700 flex">
            {(['commitments', 'decisions', 'alerts', 'retro'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-6 py-3 font-medium transition-colors ${
                  tab === t
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          <div className="p-6">
            {loading && <div className="text-center text-slate-600">Loading...</div>}
            {!loading && tab === 'commitments' && <CommitmentsTable data={commitments} />}
            {!loading && tab === 'decisions' && <DecisionsTable data={decisions} />}
            {!loading && tab === 'alerts' && <DriftAlerts data={alerts} />}
            {!loading && tab === 'retro' && <RetroPanel data={alerts} />}
          </div>
        </div>
      </div>
    </div>
  );
}
