'use client';

export interface RetroPanelProps {
  data: any[];
}

export default function RetroPanel({ data }: RetroPanelProps) {
  const receipts = data.filter(a => a.receipt);

  return (
    <div className="space-y-4">
      {receipts.length === 0 ? (
        <p className="text-slate-500 text-center py-8">No receipts generated yet</p>
      ) : (
        receipts.map((receipt, i) => (
          <div key={i} className="p-4 rounded-lg bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-2">
              {receipt.receipt?.narrative?.title || 'Accountability Receipt'}
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {receipt.receipt?.narrative?.summary}
            </p>
            {receipt.receipt?.video_url && (
              <a href={receipt.receipt.video_url} target="_blank" rel="noopener noreferrer" className="inline-block mt-3 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors">
                View Receipt Video
              </a>
            )}
          </div>
        ))
      )}
    </div>
  );
}
