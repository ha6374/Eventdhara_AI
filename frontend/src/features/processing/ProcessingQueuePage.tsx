import React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Cpu,
  RefreshCw,
  Clock,
  AlertTriangle,
  Play,
  RotateCcw,
  CheckCircle2,
  Info
} from 'lucide-react'
import { api } from '@/services/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatDate } from '@/lib/utils'

export const ProcessingQueuePage: React.FC = () => {
  const queryClient = useQueryClient()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['processing-queue'],
    queryFn: () => api.getProcessingQueue(),
    refetchInterval: 5000,
  })

  const retryMutation = useMutation({
    mutationFn: (id: number) => api.retryProcessing(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processing-queue'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      alert('Pipeline re-execution completed.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Retry failed')
    },
  })

  const items = data?.items || []

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Processing Engine Queue
            <Badge variant="pending">{items.length} Active</Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time pipeline job queue monitoring validation, hashing, Laplacian scoring, and AI classification.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh Queue
        </Button>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold uppercase text-[10px]">
                <th className="py-3 px-6">Image Filename</th>
                <th className="py-3 px-6">Current Pipeline State</th>
                <th className="py-3 px-6">Quality Check</th>
                <th className="py-3 px-6">Blur Score</th>
                <th className="py-3 px-6">Queued Timestamp</th>
                <th className="py-3 px-6 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.length > 0 ? (
                items.map((item: any) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-6 font-medium text-slate-800">
                      {item.filename}
                    </td>
                    <td className="py-3.5 px-6">
                      <Badge variant="review" dot>
                        {item.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-6">
                      <span className={`text-[11px] font-semibold ${item.quality_status === 'PASSED' ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {item.quality_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-6 font-mono text-slate-500">
                      {item.blur_score ? item.blur_score.toFixed(1) : '—'}
                    </td>
                    <td className="py-3.5 px-6 text-slate-500">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="py-3.5 px-6 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => retryMutation.mutate(item.id)}
                        isLoading={retryMutation.isPending}
                        className="gap-1.5 text-xs"
                      >
                        <RotateCcw className="w-3.5 h-3.5" /> Re-run Pipeline
                      </Button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 text-xs">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                      <span className="font-semibold text-slate-700">Queue is Clear</span>
                      <p className="text-slate-400 text-[11px]">No images waiting for processing or manual resolution.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
