import { getImageUrl, getReliableImageUrl } from '@/lib/utils';
import { SafeImage } from '@/components/ui/SafeImage';
import React, { useState, useEffect, useCallback, useMemo } from 'react'
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
  Info,
  Trash2,
  AlertTriangle,
  X,
  HelpCircle
} from 'lucide-react'
import { api } from '@/services/api'
import type { ImageItem, CategoryTreeNode } from '@/types'
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

const PREDEFINED_REASONS = [
  'Blurry Image',
  'Poor Image Quality',
  'Wrong Category',
  'Duplicate Image',
  'Screenshot',
  'Incomplete Decoration',
  'Poor Lighting',
  'Irrelevant Decoration',
  'Unwanted Watermark',
  'Other'
]

export const GalleryView: React.FC<GalleryViewProps> = ({ status, title, description }) => {
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [search, setSearch] = useState('')
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | undefined>(undefined)
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  // Continuous Fullscreen Viewer State
  const [viewerActiveIndex, setViewerActiveIndex] = useState<number | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [imageToDelete, setImageToDelete] = useState<ImageItem | null>(null)

  // Rejection Feedback Modal State
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [rejectImageId, setRejectImageId] = useState<number | null>(null)
  const [selectedReason, setSelectedReason] = useState<string>('Poor Image Quality')
  const [customFeedback, setCustomFeedback] = useState<string>('')

  // Query categories for dropdown
  const { data: categoryTree = [] } = useQuery({
    queryKey: ['category-tree'],
    queryFn: () => api.getCategoryTree(),
  })

  // Flatten category tree for select box
  const flatCategories = useMemo(() => {
    const list: { id: number; name: string }[] = []
    const traverse = (nodes: CategoryTreeNode[], prefix = '') => {
      for (const n of nodes) {
        list.push({ id: n.id, name: `${prefix}${n.name}` })
        if (n.children && n.children.length > 0) {
          traverse(n.children, `${prefix}${n.name} > `)
        }
      }
    }
    traverse(categoryTree)
    return list
  }, [categoryTree])

  // Images query
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['gallery-images', status, page, search, selectedCategoryId],
    queryFn: () =>
      api.getImages({
        status,
        category_id: selectedCategoryId,
        search: search || undefined,
        page,
        size: 24,
      }),
  })

  const items = data?.items || []
  const total = data?.total || 0
  const pages = data?.pages || 1

  // Current image in viewer
  const activeImage = viewerActiveIndex !== null && items[viewerActiveIndex] ? items[viewerActiveIndex] : null

  // Mutations
  const updateStatusMutation = useMutation({
    mutationFn: (payload: { id: number; status: string; reason?: string }) =>
      api.updateImageStatus(payload.id, payload.status, payload.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      queryClient.invalidateQueries({ queryKey: ['drive-status'] })
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Operation failed')
    },
  })

  const rejectFeedbackMutation = useMutation({
    mutationFn: (payload: { id: number; reason: string; customFeedback?: string }) =>
      api.rejectImageWithFeedback(payload.id, payload.reason, payload.customFeedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      setRejectModalOpen(false)
      setCustomFeedback('')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Rejection failed')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (imageId: number) => api.deleteImage(imageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      setDeleteConfirmOpen(false)
      setImageToDelete(null)

      // Auto-advance viewer index or close if empty
      if (viewerActiveIndex !== null) {
        if (items.length <= 1) {
          setViewerActiveIndex(null)
        } else if (viewerActiveIndex >= items.length - 1) {
          setViewerActiveIndex(Math.max(0, items.length - 2))
        }
      }
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Deletion failed')
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
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      alert(data?.message || 'Metadata generated successfully.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Metadata generation failed')
    },
  })

  const uploadDriveMutation = useMutation({
    mutationFn: (imageId: number) => api.uploadSingleToDrive(imageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery-images'] })
      queryClient.invalidateQueries({ queryKey: ['drive-status'] })
      alert('Successfully uploaded to Google Drive folder structure.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Google Drive upload failed')
    },
  })

  // Continuous Navigation handlers
  const handleNextPhoto = useCallback(() => {
    if (viewerActiveIndex !== null && items.length > 0) {
      setViewerActiveIndex((prev) => (prev !== null && prev < items.length - 1 ? prev + 1 : 0))
    }
  }, [viewerActiveIndex, items.length])

  const handlePrevPhoto = useCallback(() => {
    if (viewerActiveIndex !== null && items.length > 0) {
      setViewerActiveIndex((prev) => (prev !== null && prev > 0 ? prev - 1 : items.length - 1))
    }
  }, [viewerActiveIndex, items.length])

  const handlePromptDelete = useCallback((image: ImageItem) => {
    setImageToDelete(image)
    setDeleteConfirmOpen(true)
  }, [])

  // Keyboard navigation shortcuts
  useEffect(() => {
    if (viewerActiveIndex === null) return

    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return

      if (e.key === 'ArrowRight') {
        e.preventDefault()
        handleNextPhoto()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        handlePrevPhoto()
      } else if (e.key === 'Escape') {
        e.preventDefault()
        setViewerActiveIndex(null)
      } else if (e.key === 'Delete' && activeImage) {
        e.preventDefault()
        handlePromptDelete(activeImage)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [viewerActiveIndex, activeImage, handleNextPhoto, handlePrevPhoto, handlePromptDelete])

  const handleSelectAll = () => {
    if (selectedIds.length === items.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(items.map((i) => i.id))
    }
  }

  const toggleSelectOne = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const openRejectModal = (id: number) => {
    setRejectImageId(id)
    setSelectedReason('Poor Image Quality')
    setCustomFeedback('')
    setRejectModalOpen(true)
  }

  const handleConfirmRejection = () => {
    if (!rejectImageId) return
    rejectFeedbackMutation.mutate({
      id: rejectImageId,
      reason: selectedReason,
      customFeedback: customFeedback.trim() || undefined,
    })
  }

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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="checkbox"
            checked={items.length > 0 && selectedIds.length === items.length}
            onChange={handleSelectAll}
            className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4 ml-1 cursor-pointer"
          />

          {/* Category Filter */}
          <div className="w-56">
            <select
              value={selectedCategoryId ?? ''}
              onChange={(e) => {
                setSelectedCategoryId(e.target.value ? Number(e.target.value) : undefined)
                setPage(1)
              }}
              className="w-full px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Categories ({flatCategories.length})</option>
              {flatCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Search Input */}
          <div className="relative w-56">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search filename or reason..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {selectedIds.length > 0 && (
            <span className="text-xs text-slate-600 font-semibold bg-blue-50 text-blue-700 px-2.5 py-1 rounded-full">
              {selectedIds.length} Selected
            </span>
          )}
        </div>

        {/* Bulk Action Controls */}
        {selectedIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {status !== 'APPROVED' && (
              <Button
                size="sm"
                variant="success"
                onClick={() => bulkMutation.mutate({ image_ids: selectedIds, action: 'APPROVE' })}
                isLoading={bulkMutation.isPending}
              >
                Approve ({selectedIds.length})
              </Button>
            )}
            {status !== 'REJECTED' && (
              <Button
                size="sm"
                variant="danger"
                onClick={() => bulkMutation.mutate({ image_ids: selectedIds, action: 'REJECT' })}
                isLoading={bulkMutation.isPending}
              >
                Reject ({selectedIds.length})
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
            <Button
              size="sm"
              variant="outline"
              className="text-rose-600 hover:bg-rose-50 border-rose-200"
              onClick={() => {
                if (confirm(`Are you sure you want to delete ${selectedIds.length} selected photos permanently?`)) {
                  bulkMutation.mutate({ image_ids: selectedIds, action: 'DELETE' })
                }
              }}
            >
              <Trash2 className="w-3.5 h-3.5 mr-1 text-rose-500" /> Delete Selected
            </Button>
          </div>
        )}
      </div>

      {/* Main Display Grid / List */}
      {isLoading ? (
        <div className="p-20 text-center text-xs text-slate-400">Loading photographs...</div>
      ) : items.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-2xl border border-slate-200 shadow-xs">
          <Info className="w-8 h-8 text-slate-400 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-slate-800">No images found</h3>
          <p className="text-xs text-slate-500 mt-1">
            {selectedCategoryId ? 'No images under this category filter.' : `The ${title.toLowerCase()} is currently empty.`}
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3.5">
          {items.map((item, index) => {
            const isSelected = selectedIds.includes(item.id)
            return (
              <div
                key={item.id}
                className={`group relative bg-white rounded-xl overflow-hidden border transition-all shadow-xs hover:shadow-md ${
                  isSelected ? 'ring-2 ring-blue-600 border-blue-600' : 'border-slate-200'
                }`}
              >
                {/* Image Thumbnail */}
                <div
                  className="aspect-square bg-slate-100 overflow-hidden relative cursor-pointer"
                  onClick={() => setViewerActiveIndex(index)}
                >
                  <SafeImage
                    src={getReliableImageUrl(item)}
                    fallbackSrc={getImageUrl(item.storage_path)}
                    imageId={item.id}
                    alt={item.original_filename}
                    loading="lazy"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />

                  {/* Badges Overlay */}
                  <div className="absolute top-2 left-2 flex flex-col gap-1">
                    {item.quality_status === 'PASSED' ? (
                      <span className="bg-emerald-500/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded shadow-xs">
                        {item.blur_score ? item.blur_score.toFixed(0) : 'Sharp'}
                      </span>
                    ) : (
                      <span className="bg-rose-500/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded shadow-xs">
                        Blur
                      </span>
                    )}
                    {item.is_duplicate && (
                      <span className="bg-purple-600/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded shadow-xs">
                        Dup
                      </span>
                    )}
                  </div>

                  {/* Expand Icon */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <span className="p-2 bg-white/90 rounded-full text-slate-900 shadow">
                      <Maximize2 className="w-4 h-4" />
                    </span>
                  </div>
                </div>

                {/* Selection Checkbox */}
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleSelectOne(item.id)}
                  className="absolute top-2 right-2 rounded text-blue-600 focus:ring-blue-500 h-4 w-4 bg-white/80 cursor-pointer shadow-xs"
                />

                {/* Card Meta Footer */}
                <div className="p-2.5 text-[11px] space-y-1">
                  <div className="font-medium text-slate-900 truncate" title={item.original_filename}>
                    {item.original_filename}
                  </div>
                  <div className="text-[10px] text-slate-500 truncate">
                    {item.category_name || 'Unassigned'}
                  </div>

                  {/* Quick Card Action Buttons */}
                  <div className="pt-1.5 flex items-center justify-between border-t border-slate-100">
                    <div className="flex items-center gap-1">
                      {status !== 'APPROVED' && (
                        <button
                          onClick={() => updateStatusMutation.mutate({ id: item.id, status: 'APPROVED' })}
                          className="p-1 hover:bg-emerald-50 rounded text-emerald-600"
                          title="Quick Approve"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {status !== 'REJECTED' && (
                        <button
                          onClick={() => openRejectModal(item.id)}
                          className="p-1 hover:bg-rose-50 rounded text-rose-600"
                          title="Reject with Feedback"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                    <button
                      onClick={() => handlePromptDelete(item)}
                      className="p-1 hover:bg-rose-50 rounded text-slate-400 hover:text-rose-600"
                      title="Delete Image"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        /* List Mode */
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 border-b text-slate-700 font-semibold text-[11px] uppercase tracking-wider">
              <tr>
                <th className="p-3 w-8">
                  <input
                    type="checkbox"
                    checked={items.length > 0 && selectedIds.length === items.length}
                    onChange={handleSelectAll}
                    className="rounded text-blue-600"
                  />
                </th>
                <th className="p-3 w-16">Preview</th>
                <th className="p-3">Filename</th>
                <th className="p-3">Category</th>
                <th className="p-3">Dimensions</th>
                <th className="p-3">Blur Score</th>
                <th className="p-3">Reason / Details</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item, index) => (
                <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                  <td className="p-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.id)}
                      onChange={() => toggleSelectOne(item.id)}
                      className="rounded text-blue-600"
                    />
                  </td>
                  <td className="p-3">
                    <SafeImage
                      src={getReliableImageUrl(item)}
                      fallbackSrc={getImageUrl(item.storage_path)}
                      imageId={item.id}
                      alt={item.original_filename}
                      className="w-10 h-10 object-cover rounded cursor-pointer"
                      onClick={() => setViewerActiveIndex(index)}
                      showMissingBadge={false}
                    />
                  </td>
                  <td className="p-3 font-medium text-slate-900">
                    <button
                      onClick={() => setViewerActiveIndex(index)}
                      className="hover:underline text-left"
                    >
                      {item.original_filename}
                    </button>
                  </td>
                  <td className="p-3 text-slate-600">{item.category_name || 'â€”'}</td>
                  <td className="p-3 font-mono">{item.width}x{item.height}</td>
                  <td className="p-3 font-mono">
                    {item.blur_score ? item.blur_score.toFixed(1) : 'â€”'}
                  </td>
                  <td className="p-3 max-w-xs truncate text-[11px] text-slate-500">
                    {item.rejection_reason || item.review_reason || 'â€”'}
                  </td>
                  <td className="p-3 text-right space-x-1.5">
                    {status !== 'APPROVED' && (
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => updateStatusMutation.mutate({ id: item.id, status: 'APPROVED' })}
                      >
                        Approve
                      </Button>
                    )}
                    {status !== 'REJECTED' && (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => openRejectModal(item.id)}
                      >
                        Reject
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-rose-600 hover:bg-rose-50"
                      onClick={() => handlePromptDelete(item)}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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

      {/* PHASE 6: CONTINUOUS FULL-SCREEN PHOTO VIEWER MODAL */}
      {activeImage && (
        <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-sm flex flex-col justify-between text-white p-4 sm:p-6 animate-in fade-in duration-200">
          {/* Top Bar */}
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold tracking-wide text-slate-200">
                Photo {viewerActiveIndex! + 1} / {items.length}
              </span>
              <span className="text-slate-500">|</span>
              <span className="text-xs text-slate-300 font-medium truncate max-w-sm">
                {activeImage.original_filename}
              </span>
              <Badge variant={status === 'APPROVED' ? 'approved' : status === 'REJECTED' ? 'rejected' : 'review'}>
                {activeImage.status}
              </Badge>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden md:inline text-[11px] text-slate-400">
                Shortcuts: â† Prev | â†’ Next | Del Delete | Esc Close
              </span>
              <button
                onClick={() => setViewerActiveIndex(null)}
                className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                title="Close Viewer (Escape)"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Main Viewer Body with Previous / Next Continuous Buttons */}
          <div className="relative flex-1 flex items-center justify-center my-3 overflow-hidden">
            {/* Previous Button */}
            <button
              onClick={handlePrevPhoto}
              className="absolute left-2 sm:left-4 z-10 p-3 rounded-full bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm transition-transform active:scale-95 shadow-lg border border-white/10"
              title="Previous Photo (Left Arrow)"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>

            {/* High-Resolution Center Image Preview */}
            <div className="max-h-[75vh] max-w-[85vw] flex items-center justify-center">
              <SafeImage
                src={getReliableImageUrl(activeImage)}
                fallbackSrc={getImageUrl(activeImage.storage_path)}
                imageId={activeImage.id}
                alt={activeImage.original_filename}
                className="max-h-[75vh] max-w-[85vw] object-contain rounded-lg shadow-2xl"
                containerClassName="min-w-[320px] min-h-[240px]"
              />
            </div>

            {/* Next Button */}
            <button
              onClick={handleNextPhoto}
              className="absolute right-2 sm:right-4 z-10 p-3 rounded-full bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm transition-transform active:scale-95 shadow-lg border border-white/10"
              title="Next Photo (Right Arrow)"
            >
              <ChevronRight className="w-6 h-6" />
            </button>
          </div>

          {/* Bottom Action & Telemetry Bar */}
          <div className="pt-3 border-t border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex flex-wrap items-center gap-4 text-slate-300">
              <span>Category: <strong className="text-white">{activeImage.category_name || 'Unassigned'}</strong></span>
              <span>Dimensions: <strong className="text-white">{activeImage.width}x{activeImage.height}</strong></span>
              <span>Blur Score: <strong className="text-white">{activeImage.blur_score ? activeImage.blur_score.toFixed(1) : 'â€”'}</strong></span>
              {activeImage.rejection_reason && (
                <span className="text-rose-300 font-medium truncate max-w-md">
                  Reason: {activeImage.rejection_reason}
                </span>
              )}
            </div>

            {/* Operator Actions in Fullscreen Viewer */}
            <div className="flex items-center gap-2">
              {activeImage.status !== 'APPROVED' && (
                <Button
                  size="sm"
                  variant="success"
                  onClick={() => updateStatusMutation.mutate({ id: activeImage.id, status: 'APPROVED' })}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Approve
                </Button>
              )}
              {activeImage.status !== 'REJECTED' && (
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => openRejectModal(activeImage.id)}
                >
                  <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
                </Button>
              )}
              {activeImage.status === 'APPROVED' && (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-white/20 text-white hover:bg-white/10"
                    onClick={() => generateMetaMutation.mutate(activeImage.id)}
                  >
                    Generate Metadata
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => uploadDriveMutation.mutate(activeImage.id)}
                  >
                    Sync to Drive
                  </Button>
                </>
              )}
              <Button
                size="sm"
                variant="outline"
                className="border-rose-500/50 text-rose-400 hover:bg-rose-500/20"
                onClick={() => handlePromptDelete(activeImage)}
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" /> Delete Photo
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* PHASE 7: STRUCTURED REJECTION FEEDBACK MODAL */}
      <Modal
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Image Rejection & Quality Feedback"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Please choose a verified rejection cause. The AI learning engine analyzes this feedback to refine future category evaluations.
          </p>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Select Primary Rejection Cause
            </label>
            <div className="grid grid-cols-2 gap-2">
              {PREDEFINED_REASONS.map((reason) => (
                <button
                  key={reason}
                  type="button"
                  onClick={() => setSelectedReason(reason)}
                  className={`text-left px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                    selectedReason === reason
                      ? 'bg-rose-50 border-rose-400 text-rose-800'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {reason}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Custom Detailed Feedback (Optional)
            </label>
            <textarea
              rows={3}
              value={customFeedback}
              onChange={(e) => setCustomFeedback(e.target.value)}
              placeholder="e.g. Backdrop contains Birthday balloons instead of Wedding stage props..."
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-rose-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRejectModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={handleConfirmRejection}
              isLoading={rejectFeedbackMutation.isPending}
            >
              Confirm Rejection & Submit Feedback
            </Button>
          </div>
        </div>
      </Modal>

      {/* PERMANENT DELETION CONFIRMATION MODAL */}
      <Modal
        isOpen={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Confirm Permanent Deletion"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-900">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div className="text-xs">
              <span className="font-semibold block">Are you sure you want to permanently delete this photo?</span>
              <p className="mt-1 text-slate-600 font-mono text-[11px]">
                {imageToDelete?.original_filename} (ID: #{imageToDelete?.id})
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                This action will delete the image from database, local category folders, and Google Drive. A permanent deletion audit log will be retained.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                if (imageToDelete) {
                  deleteMutation.mutate(imageToDelete.id)
                }
              }}
              isLoading={deleteMutation.isPending}
            >
              Permanently Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
