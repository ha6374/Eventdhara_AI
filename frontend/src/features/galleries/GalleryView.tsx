import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Grid,
  List as ListIcon,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  Clock,
  Eye,
  Maximize2,
  Layers,
  Sparkles,
  Cloud,
  FileSpreadsheet,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Info
} from 'lucide-react'
import { api } from '@/services/api'
import type { ImageItem } from '@/types'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { formatBytes, formatDate } from '@/lib/utils'

interface GalleryViewProps {
  status: 'APPROVED' | 'REVIEW_REQUIRED' | 'REJECTED'
  title: string
  description: string
}

export const GalleryView: React.FC<GalleryViewProps> = ({ status, title, description }) => {
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [inspectImage, setInspectImage] = useState<ImageItem | null>(null)
  const [reasonModal, setReasonModal] = useState<{ isOpen: boolean; action: string; imageId?: number }>({
    isOpen: false,
    action: '',
  })
  const [actionReason, setActionReason] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['gallery-images', status, page, search],
    queryFn: () =>
      api.getImages({
        status,
        search: search || undefined,
        page,
        size: 24,
      }),
  })

  // Mutations
  const updateStatusMutation = useMutation({
    mutationFn: (payload: { id: number; status: string; reason?: string }) =>
      api.updateImageStatus(payload.id, payload.status, payload.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      setInspectImage(null)
      setReasonModal({ isOpen: false, action: '' })
      setActionReason('')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Operation failed')
    },
  })

  const bulkMutation = useMutation({
    mutationFn: (payload: { image_ids: number[]; action: string; reason?: string }) =>
      api.bulkImageAction(payload.image_ids, payload.action, payload.reason),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      setSelectedIds([])
      if (res.messages && res.messages.length > 0) {
        alert(res.messages.join('\n'))
      }
    },
  })

  const generateMetaMutation = useMutation({
    mutationFn: (imageId: number) => api.generateMetadata(imageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      alert('Metadata generated successfully.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Metadata generation failed')
    },
  })

  const uploadDriveMutation = useMutation({
    mutationFn: (imageId: number) => api.uploadSingleToDrive(imageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      alert('Successfully uploaded to Google Drive folder structure.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Google Drive upload failed')
    },
  })

  const handleSelectAll = () => {
    if (!data?.items) return
    if (selectedIds.length === data.items.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(data.items.map((i) => i.id))
    }
  }

  const toggleSelectOne = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const handleQuickApprove = (id: number) => {
    updateStatusMutation.mutate({ id, status: 'APPROVED' })
  }

  const handleOpenReject = (id: number) => {
    setReasonModal({ isOpen: true, action: 'REJECT', imageId: id })
  }

  const items = data?.items || []
  const total = data?.total || 0
  const pages = data?.pages || 1

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            {title}
            <Badge variant={status === 'APPROVED' ? 'approved' : status === 'REJECTED' ? 'rejected' : 'review'}>
              {total} Photos
            </Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">{description}</p>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2.5">
          {/* View toggle */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md ${viewMode === 'grid' ? 'bg-white shadow-xs text-blue-600' : 'text-slate-500'}`}
              title="Grid View"
            >
              <Grid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-md ${viewMode === 'list' ? 'bg-white shadow-xs text-blue-600' : 'text-slate-500'}`}
              title="List View"
            >
              <ListIcon className="w-4 h-4" />
            </button>
          </div>

          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter and Bulk Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={items.length > 0 && selectedIds.length === items.length}
            onChange={handleSelectAll}
            className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4 ml-1 cursor-pointer"
          />
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search filename or reason..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          {selectedIds.length > 0 && (
            <span className="text-xs text-slate-600 font-semibold bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
              {selectedIds.length} Selected
            </span>
          )}
        </div>

        {/* Bulk Action Controls */}
        {selectedIds.length > 0 && (
          <div className="flex items-center gap-2">
            {status !== 'APPROVED' && (
              <Button
                size="sm"
                variant="success"
                onClick={() => bulkMutation.mutate({ image_ids: selectedIds, action: 'APPROVE' })}
                isLoading={bulkMutation.isPending}
              >
                Approve Selected
              </Button>
            )}
            {status !== 'REJECTED' && (
              <Button
                size="sm"
                variant="danger"
                onClick={() => bulkMutation.mutate({ image_ids: selectedIds, action: 'REJECT' })}
                isLoading={bulkMutation.isPending}
              >
                Reject Selected
              </Button>
            )}
            {status === 'APPROVED' && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => bulkMutation.mutate({ image_ids: selectedIds, action: 'GENERATE_METADATA' })}
                >
                  <FileSpreadsheet className="w-3.5 h-3.5 mr-1" /> Generate Metadata
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => bulkMutation.mutate({ image_ids: selectedIds, action: 'UPLOAD_DRIVE' })}
                >
                  <Cloud className="w-3.5 h-3.5 mr-1" /> Sync to Drive
                </Button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Main Display Grid / List */}
      {isLoading ? (
        <div className="flex items-center justify-center p-16 text-slate-400 text-xs">
          Loading gallery items...
        </div>
      ) : items.length > 0 ? (
        viewMode === 'grid' ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {items.map((item) => (
              <div
                key={item.id}
                className={`group relative bg-white rounded-xl border overflow-hidden shadow-xs transition-all hover:shadow-md ${
                  selectedIds.includes(item.id) ? 'border-blue-600 ring-2 ring-blue-500/30' : 'border-slate-200'
                }`}
              >
                {/* Checkbox overlay */}
                <div className="absolute top-2 left-2 z-10">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => toggleSelectOne(item.id)}
                    className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4 bg-white/90 border-slate-300 shadow-xs cursor-pointer"
                  />
                </div>

                {/* Image Thumbnail */}
                <div
                  className="aspect-square bg-slate-100 overflow-hidden relative cursor-pointer"
                  onClick={() => setInspectImage(item)}
                >
                  <img
                    src={`/${item.storage_path}`}
                    alt={item.original_filename}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    loading="lazy"
                    onError={(e) => {
                      // Fallback placeholder
                      (e.target as HTMLElement).style.display = 'none'
                    }}
                  />
                  <div className="absolute inset-0 bg-slate-900/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        setInspectImage(item)
                      }}
                      className="p-1.5 rounded-lg bg-white/90 text-slate-800 hover:bg-white shadow-xs"
                      title="Inspect Details"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Details Footer */}
                <div className="p-2.5 space-y-1">
                  <span className="font-semibold text-slate-800 text-xs truncate block" title={item.original_filename}>
                    {item.original_filename}
                  </span>
                  <div className="flex items-center justify-between text-[10px] text-slate-500">
                    <span className="truncate max-w-[80px] font-medium text-slate-600">
                      {item.category_name || 'Unassigned'}
                    </span>
                    <span className="font-mono">{item.width}x{item.height}</span>
                  </div>

                  {/* Actions according to status */}
                  <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between gap-1">
                    {status === 'REVIEW_REQUIRED' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleQuickApprove(item.id)}
                          className="flex-1 py-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded text-center"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => handleOpenReject(item.id)}
                          className="flex-1 py-1 text-[11px] font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 rounded text-center"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {status === 'APPROVED' && (
                      <span className="text-[10px] text-slate-400 truncate">
                        Drive: {item.drive_status}
                      </span>
                    )}
                    {status === 'REJECTED' && (
                      <span className="text-[10px] text-rose-600 truncate" title={item.rejection_reason || ''}>
                        {item.rejection_reason || 'Rejected'}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* List View */
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold uppercase text-[10px]">
                    <th className="py-3 px-4 w-10"></th>
                    <th className="py-3 px-4">Filename</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Resolution</th>
                    <th className="py-3 px-4">Blur Score</th>
                    <th className="py-3 px-4">Metadata</th>
                    <th className="py-3 px-4">Drive</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.id)}
                          onChange={() => toggleSelectOne(item.id)}
                          className="rounded text-blue-600 h-4 w-4"
                        />
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-800 flex items-center gap-2">
                        <img
                          src={`/${item.storage_path}`}
                          alt=""
                          className="w-8 h-8 rounded object-cover bg-slate-100"
                        />
                        <span className="truncate max-w-[200px]">{item.original_filename}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-600 font-medium">
                        {item.category_name || 'Unassigned'}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-500">
                        {item.width}x{item.height}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-500">
                        {item.blur_score ? item.blur_score.toFixed(1) : '—'}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={item.metadata_status === 'COMPLETED' ? 'approved' : 'neutral'}>
                          {item.metadata_status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={item.drive_status === 'COMPLETED' ? 'approved' : 'neutral'}>
                          {item.drive_status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-right space-x-2">
                        <button
                          type="button"
                          onClick={() => setInspectImage(item)}
                          className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                          View
                        </button>
                        {status === 'REVIEW_REQUIRED' && (
                          <>
                            <button
                              type="button"
                              onClick={() => handleQuickApprove(item.id)}
                              className="text-emerald-600 hover:text-emerald-800 font-medium ml-2"
                            >
                              Approve
                            </button>
                            <button
                              type="button"
                              onClick={() => handleOpenReject(item.id)}
                              className="text-rose-600 hover:text-rose-800 font-medium ml-2"
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      ) : (
        <Card className="p-16 text-center text-slate-400">
          <div className="flex flex-col items-center justify-center gap-2">
            <Info className="w-8 h-8 text-slate-300" />
            <h3 className="text-sm font-semibold text-slate-700">No images in this gallery</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              Photos sorted into {status.toLowerCase().replace('_', ' ')} will appear here automatically.
            </p>
          </div>
        </Card>
      )}

      {/* Pagination Controls */}
      {pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-slate-500">
            Page {page} of {pages} ({total} total items)
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
            >
              Next <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Detail Inspector Modal */}
      {inspectImage && (
        <Modal
          isOpen={!!inspectImage}
          onClose={() => setInspectImage(null)}
          title={`Image Details: ${inspectImage.original_filename}`}
          maxWidth="4xl"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Full preview */}
            <div className="bg-slate-900 rounded-xl overflow-hidden flex items-center justify-center min-h-[300px]">
              <img
                src={`/${inspectImage.storage_path}`}
                alt={inspectImage.original_filename}
                className="max-h-[450px] w-auto object-contain"
              />
            </div>

            {/* Detailed metadata specs */}
            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <span className="text-slate-500">Pipeline Status</span>
                <Badge variant={status === 'APPROVED' ? 'approved' : status === 'REJECTED' ? 'rejected' : 'review'} dot>
                  {inspectImage.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-50 rounded-lg">
                  <span className="text-slate-500 text-[10px] uppercase font-semibold">Dimensions</span>
                  <div className="font-mono text-slate-800 font-bold mt-0.5">{inspectImage.width} x {inspectImage.height}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg">
                  <span className="text-slate-500 text-[10px] uppercase font-semibold">File Size</span>
                  <div className="font-mono text-slate-800 font-bold mt-0.5">{formatBytes(inspectImage.file_size)}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg">
                  <span className="text-slate-500 text-[10px] uppercase font-semibold">Blur Score (Laplacian)</span>
                  <div className="font-mono text-slate-800 font-bold mt-0.5">
                    {inspectImage.blur_score ? inspectImage.blur_score.toFixed(1) : '—'}
                  </div>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg">
                  <span className="text-slate-500 text-[10px] uppercase font-semibold">Quality Status</span>
                  <div className="text-slate-800 font-bold mt-0.5">{inspectImage.quality_status}</div>
                </div>
              </div>

              {/* Duplicate Information if any */}
              {inspectImage.is_duplicate && (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-purple-900">
                  <span className="font-semibold block">Duplicate Flagged</span>
                  <p className="text-[11px] mt-0.5">
                    Matches reference #{inspectImage.duplicate_of_id} with {inspectImage.duplicate_similarity?.toFixed(1)}% similarity.
                  </p>
                </div>
              )}

              {/* Reasons if any */}
              {inspectImage.rejection_reason && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-900">
                  <span className="font-semibold block">Rejection Cause</span>
                  <p className="text-[11px] mt-0.5">{inspectImage.rejection_reason}</p>
                </div>
              )}

              {inspectImage.review_reason && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900">
                  <span className="font-semibold block">Review Flag Cause</span>
                  <p className="text-[11px] mt-0.5">{inspectImage.review_reason}</p>
                </div>
              )}

              {/* Hashes */}
              <div className="space-y-1 text-[11px]">
                <div className="truncate">
                  <span className="text-slate-400 font-mono">SHA256: </span>
                  <span className="font-mono text-slate-600">{inspectImage.sha256}</span>
                </div>
                <div className="truncate">
                  <span className="text-slate-400 font-mono">pHash: </span>
                  <span className="font-mono text-slate-600">{inspectImage.phash}</span>
                </div>
              </div>

              {/* Action Buttons in Modal */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2">
                {inspectImage.status !== 'APPROVED' && (
                  <Button
                    size="sm"
                    variant="success"
                    onClick={() => handleQuickApprove(inspectImage.id)}
                  >
                    Approve
                  </Button>
                )}
                {inspectImage.status !== 'REJECTED' && (
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => handleOpenReject(inspectImage.id)}
                  >
                    Reject
                  </Button>
                )}
                {inspectImage.status === 'APPROVED' && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => generateMetaMutation.mutate(inspectImage.id)}
                      isLoading={generateMetaMutation.isPending}
                    >
                      Generate Metadata
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => uploadDriveMutation.mutate(inspectImage.id)}
                      isLoading={uploadDriveMutation.isPending}
                    >
                      Upload to Drive
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Rejection / Review Reason Modal */}
      <Modal
        isOpen={reasonModal.isOpen}
        onClose={() => setReasonModal({ isOpen: false, action: '' })}
        title="Specify Decision Reason"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Please enter a descriptive explanation for audit logging and quality feedback records.
          </p>
          <textarea
            rows={3}
            value={actionReason}
            onChange={(e) => setActionReason(e.target.value)}
            placeholder="e.g. Blurry foreground, mismatched decoration category, non-event photo..."
            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
          <div className="flex items-center justify-end gap-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReasonModal({ isOpen: false, action: '' })}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                if (reasonModal.imageId) {
                  updateStatusMutation.mutate({
                    id: reasonModal.imageId,
                    status: 'REJECTED',
                    reason: actionReason,
                  })
                }
              }}
            >
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
