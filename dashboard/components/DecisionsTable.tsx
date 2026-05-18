'use client';

export interface DecisionsTableProps {
  data: any[];
}

export default function DecisionsTable({ data }: DecisionsTableProps) {
  return (
    <div className="space-y-4">
      {data.length === 0 ? (
        <p className="text-slate-500 text-center py-8">No decisions yet</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="text-left py-3 px-4 font-semibold text-slate-900 dark:text-white">Decision</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900 dark:text-white">Watch Terms</th>
                <th className="text-left py-3 px-4 font-semibold text-slate-900 dark:text-white">Category</th>
              </tr>
            </thead>
            <tbody>
              {data.map((decision, i) => (
                <tr key={i} className="border-b border-slate-100 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50">
                  <td className="py-3 px-4 text-slate-700 dark:text-slate-300">{decision.text}</td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-2">
                      {decision.watch_terms?.map((term: string, j: number) => (
                        <span key={j} className="inline-block px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs rounded">
                          {term}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-slate-600 dark:text-slate-400 text-xs">{decision.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
