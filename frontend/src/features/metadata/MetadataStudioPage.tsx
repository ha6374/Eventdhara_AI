import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileSpreadsheet,
  Sparkles,
  Download,
  Edit2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Tag,
  HelpCircle,
  CheckSquare,
  FileText
} from 'lucide-react'
import { api } from '@/services/api'
import type { ImageMetadata } from '@/types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { formatDate } from '@/lib/utils'

export const MetadataStudioPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [selectedMeta, setSelectedMeta] = useState<ImageMetadata | null>(null)
  const [editModalOpen, setEditModalOpen] = useState(false)

  // Edit form state
  const [editName, setEditName] = useState('')
  const [editShortDesc, setEditShortDesc] = useState('')
  const [editLongDesc, setEditLongDesc] = useState('')
  const [editNote, setEditNote] = useState('')

  const { data: metadataList = [], isLoading, refetch } = useQuery({
    queryKey: ['all-metadata'],
    queryFn: () => api.getAllMetadata(),
  })

  const bulkGenerateMutation = useMutation({
    mutationFn: () => api.bulkGenerateMetadata(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['all-metadata'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
      alert(`Bulk metadata generation complete: ${data.completed} completed, ${data.failed} failed.`)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Bulk generation failed')
    },
  })

  const updateMetaMutation = useMutation({
    mutationFn: (payload: { id: number; data: Partial<ImageMetadata> }) =>
      api.updateMetadata(payload.id, payload.data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['all-metadata'] })
      setSelectedMeta(updated)
      setEditModalOpen(false)
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Update failed')
    },
  })

  const handleOpenEdit = (meta: ImageMetadata) => {
    setSelectedMeta(meta)
    setEditName(meta.name)
    setEditShortDesc(meta.short_description)
    setEditLongDesc(meta.long_description)
    setEditNote(meta.note || '')
    setEditModalOpen(true)
  }

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedMeta) return
    updateMetaMutation.mutate({
      id: selectedMeta.id,
      data: {
        name: editName,
        short_description: editShortDesc,
        long_description: editLongDesc,
        note: editNote,
      },
    })
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Metadata Studio
            <Badge variant="approved">{metadataList.length} Catalog Records</Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enterprise copywriting engine for approved decoration photographs. Strictly derives visible styling elements.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={() => bulkGenerateMutation.mutate()}
            isLoading={bulkGenerateMutation.isPending}
            className="gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Bulk Generate Approved
          </Button>
          <a href="/api/v1/reports/export?format=excel&status=APPROVED" download>
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="w-4 h-4" />
              Export Excel Catalog
            </Button>
          </a>
        </div>
      </div>

      {/* Main Layout */}
      {isLoading ? (
        <div className="flex items-center justify-center p-16 text-slate-400 text-xs">
          Loading catalog metadata records...
        </div>
      ) : metadataList.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {metadataList.map((meta) => (
            <Card key={meta.id} className="flex flex-col justify-between hover:border-slate-300 transition-all shadow-xs">
              <div>
                <CardHeader className="p-4 border-b bg-slate-50/50 flex-row items-center justify-between">
                  <div className="truncate">
                    <span className="font-semibold text-xs text-slate-800 truncate block">
                      {meta.name}
                    </span>
                    <span className="text-[10px] text-slate-400 truncate block">
                      Photo: {meta.image_filename || `#${meta.image_id}`}
                    </span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleOpenEdit(meta)} className="p-1 h-7">
                    <Edit2 className="w-3.5 h-3.5 text-slate-600" />
                  </Button>
                </CardHeader>

                <CardContent className="p-4 space-y-3 text-xs">
                  {/* Image preview thumbnail */}
                  {meta.image_url && (
                    <div className="h-32 bg-slate-100 rounded-lg overflow-hidden">
                      <img
                        src={`/${meta.image_url}`}
                        alt={meta.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  )}

                  <div>
                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                      Short Description
                    </span>
                    <p className="text-slate-700 text-xs mt-0.5 line-clamp-2">
                      {meta.short_description}
                    </p>
                  </div>

                  {/* Inclusions summary */}
                  {meta.inclusion && meta.inclusion.length > 0 && (
                    <div>
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                        Visible Inclusions
                      </span>
                      <ul className="mt-1 space-y-0.5 text-[11px] text-slate-600 list-disc list-inside">
                        {meta.inclusion.slice(0, 3).map((inc, i) => (
                          <li key={i} className="truncate">{inc}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Tags */}
                  {meta.tags && meta.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {meta.tags.slice(0, 4).map((tag, i) => (
                        <span
                          key={i}
                          className="bg-slate-100 text-slate-600 text-[10px] px-2 py-0.5 rounded font-medium"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </div>

              <div className="p-3 border-t border-slate-100 bg-slate-50/30 flex items-center justify-between text-[10px] text-slate-400">
                <span>Updated: {formatDate(meta.updated_at)}</span>
                <span className="text-blue-600 font-semibold cursor-pointer" onClick={() => handleOpenEdit(meta)}>
                  View Full Specs & Edit →
                </span>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-16 text-center text-slate-400">
          <div className="flex flex-col items-center justify-center gap-2">
            <FileSpreadsheet className="w-8 h-8 text-slate-300" />
            <h3 className="text-sm font-semibold text-slate-700">No metadata records generated yet</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              Approve decoration photographs in the Review Queue or Approved Gallery, then click "Bulk Generate Approved".
            </p>
          </div>
        </Card>
      )}

      {/* Edit Specs Modal */}
      {selectedMeta && (
        <Modal
          isOpen={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          title={`Edit Product Specs: ${selectedMeta.name}`}
          maxWidth="2xl"
        >
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Product Title *</label>
              <input
                type="text"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Short Description *</label>
              <textarea
                rows={2}
                required
                value={editShortDesc}
                onChange={(e) => setEditShortDesc(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Comprehensive Long Description *</label>
              <textarea
                rows={4}
                required
                value={editLongDesc}
                onChange={(e) => setEditLongDesc(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Operational Logistics Note</label>
              <input
                type="text"
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button type="button" variant="outline" size="sm" onClick={() => setEditModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" isLoading={updateMetaMutation.isPending}>
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
