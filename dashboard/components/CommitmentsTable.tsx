'use client';

export interface CommitmentsTableProps {
  data: any[];
}

export default function CommitmentsTable({ data }: CommitmentsTableProps) {
  return (
    <div className="space-y-4">
      {data.length === 0 ? (
        <p className="text-slate-500 text-center py-8">No commitments yet</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="text-left py-3 px-4 font-semibold text-slate-900 dark:text-white">Text</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900 dark:text-white">Confidence</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900 dark:text-white">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((commitment, i) => (
                <tr key={i} className="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50">
                  <td className="py-3 px-4 text-slate-700 dark:text-slate-300">{commitment.text}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 bg-slate-200 dark:bg-slate-600 rounded">
                        <div 
                          className="h-full bg-blue-500 rounded" 
                          style={{ width: `${(commitment.confidence_score || 0) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium">{Math.round((commitment.confidence_score || 0) * 100)}%</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-block px-3 py-1 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
                      Active
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
