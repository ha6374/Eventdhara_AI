import React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CopyCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  ArrowRight,
  ShieldAlert,
  Percent
} from 'lucide-react'
import { api } from '@/services/api'
import type { DuplicateComparisonItem } from '@/types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatBytes, formatDate } from '@/lib/utils'

export const DuplicatePage: React.FC = () => {
  const queryClient = useQueryClient()

  const { data: duplicates = [], isLoading, refetch } = useQuery({
    queryKey: ['duplicates-list'],
    queryFn: () => api.getDuplicates(),
  })

  const resolveMutation = useMutation({
    mutationFn: (payload: { id: number; action: 'KEEP_AS_DUPLICATE' | 'FORCE_APPROVE' | 'REJECT' }) =>
      api.resolveDuplicate(payload.id, payload.action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicates-list'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Resolution action failed')
    },
  })

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Duplicate Center
            <Badge variant="duplicate">{duplicates.length} Flagged Pairs</Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Global perceptual pHash and exact cryptographic SHA256 duplicate detection across all current and archived collections.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Refresh Matches
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center p-16 text-slate-400 text-xs">
          Loading duplicate pairs...
        </div>
      ) : duplicates.length > 0 ? (
        <div className="space-y-6">
          {duplicates.map((item, idx) => {
            const dup = item.duplicate_image
            const orig = item.original_image

            return (
              <Card key={`dup-${dup.id}-${idx}`} className="border-purple-200 shadow-xs">
                <CardHeader className="bg-purple-50/40 border-b border-purple-100 flex-row items-center justify-between py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-purple-900">
                      Comparison Pair #{idx + 1}
                    </span>
                    <Badge variant="duplicate">
                      {item.duplicate_type === 'SHA256_EXACT' ? '100% Cryptographic Match' : `${item.similarity_percentage}% Visual Similarity`}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="success"
                      onClick={() => resolveMutation.mutate({ id: dup.id, action: 'FORCE_APPROVE' })}
                      isLoading={resolveMutation.isPending}
                    >
                      Override: Distinct Photo
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => resolveMutation.mutate({ id: dup.id, action: 'REJECT' })}
                      isLoading={resolveMutation.isPending}
                    >
                      Confirm Reject Duplicate
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
                    {/* Left: Original Reference Image */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider text-[10px]">
                          Existing Canonical Reference
                        </span>
                        {orig && <Badge variant="approved">Status: {orig.status}</Badge>}
                      </div>

                      {orig ? (
                        <div className="bg-slate-900 rounded-xl overflow-hidden aspect-video relative flex items-center justify-center">
                          <img
                            src={`/${orig.storage_path}`}
                            alt={orig.original_filename}
                            className="w-full h-full object-contain"
                          />
                        </div>
                      ) : (
                        <div className="aspect-video bg-slate-100 rounded-xl flex items-center justify-center text-slate-400 text-xs">
                          Reference record no longer active
                        </div>
                      )}

                      {orig && (
                        <div className="p-3 bg-slate-50 rounded-lg text-xs space-y-1">
                          <div className="font-semibold text-slate-800 truncate">{orig.original_filename}</div>
                          <div className="text-slate-500 text-[11px] flex items-center justify-between">
                            <span>Category: {orig.category_name || 'Unassigned'}</span>
                            <span>{orig.width}x{orig.height} • {formatBytes(orig.file_size)}</span>
                          </div>
                          <div className="text-slate-400 text-[10px] font-mono truncate">pHash: {orig.phash}</div>
                        </div>
                      )}
                    </div>

                    {/* Right: Newly Detected Duplicate */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-purple-700 uppercase tracking-wider text-[10px]">
                          Newly Ingested Candidate
                        </span>
                        <Badge variant="duplicate">Status: DUPLICATE</Badge>
                      </div>

                      <div className="bg-slate-900 rounded-xl overflow-hidden aspect-video relative flex items-center justify-center border-2 border-purple-400">
                        <img
                          src={`/${dup.storage_path}`}
                          alt={dup.original_filename}
                          className="w-full h-full object-contain"
                        />
                      </div>

                      <div className="p-3 bg-purple-50/60 rounded-lg text-xs space-y-1 border border-purple-100">
                        <div className="font-semibold text-purple-950 truncate">{dup.original_filename}</div>
                        <div className="text-purple-700 text-[11px] flex items-center justify-between">
                          <span>Ingested: {formatDate(dup.created_at)}</span>
                          <span>{dup.width}x{dup.height} • {formatBytes(dup.file_size)}</span>
                        </div>
                        <div className="text-purple-500 text-[10px] font-mono truncate">pHash: {dup.phash}</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : (
        <Card className="p-16 text-center text-slate-400">
          <div className="flex flex-col items-center justify-center gap-2">
            <CopyCheck className="w-8 h-8 text-slate-300" />
            <h3 className="text-sm font-semibold text-slate-700">No duplicate images found</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              All ingested decoration photographs currently have distinct perceptual hashes and unique SHA256 checksums.
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}
