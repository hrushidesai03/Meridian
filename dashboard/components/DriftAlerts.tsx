'use client';

export interface DriftAlertsProps {
  data: any[];
}

export default function DriftAlerts({ data }: DriftAlertsProps) {
  // Display all alerts, not just drift (to show what's actually being returned)
  const allAlerts = Array.isArray(data) ? data : [];
  
  // Count by type
  const driftAlerts = allAlerts.filter(a => a.alert_type === 'drift');
  const gapAlerts = allAlerts.filter(a => a.alert_type === 'gap');
  const unknownAlerts = allAlerts.filter(a => !a.alert_type || (a.alert_type !== 'drift' && a.alert_type !== 'gap'));

  return (
    <div className="space-y-4">
      {allAlerts.length === 0 ? (
        <p className="text-slate-500 text-center py-8">No alerts</p>
      ) : (
        <>
          {driftAlerts.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Drift Alerts ({driftAlerts.length})</h3>
              {driftAlerts.map((alert, i) => (
                <div key={i} className={`p-4 rounded-lg border-l-4 ${alert.severity === 'high' ? 'bg-red-50 dark:bg-red-900/20 border-red-500' : alert.severity === 'medium' ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-500' : 'bg-blue-50 dark:bg-blue-900/20 border-blue-500'}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-slate-900 dark:text-white">{alert.drift_description || 'Drift Detected'}</h3>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">{alert.drift_evidence || alert.alert_message || ''}</p>
                    </div>
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ml-2 flex-shrink-0 ${alert.severity === 'high' ? 'bg-red-200 dark:bg-red-800 text-red-700 dark:text-red-200' : alert.severity === 'medium' ? 'bg-yellow-200 dark:bg-yellow-800 text-yellow-700 dark:text-yellow-200' : 'bg-blue-200 dark:bg-blue-800 text-blue-700 dark:text-blue-200'}`}>
                      {(alert.severity || 'medium').toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          {gapAlerts.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Gap Alerts ({gapAlerts.length})</h3>
              {gapAlerts.map((alert, i) => (
                <div key={`gap-${i}`} className="p-4 rounded-lg border-l-4 bg-orange-50 dark:bg-orange-900/20 border-orange-500">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-slate-900 dark:text-white">{alert.gap_description || alert.alert_message || 'Gap Alert'}</h3>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">{alert.gap_evidence || ''}</p>
                    </div>
                    <span className="inline-block px-3 py-1 rounded-full text-xs font-medium ml-2 flex-shrink-0 bg-orange-200 dark:bg-orange-800 text-orange-700 dark:text-orange-200">
                      GAP
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          {unknownAlerts.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">Other Alerts ({unknownAlerts.length})</h3>
              {unknownAlerts.map((alert, i) => (
                <div key={`unknown-${i}`} className="p-4 rounded-lg border-l-4 bg-slate-50 dark:bg-slate-900/20 border-slate-500">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-slate-900 dark:text-white">{alert.alert_message || alert.message || 'Alert'}</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">Type: {alert.alert_type || 'unknown'}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
