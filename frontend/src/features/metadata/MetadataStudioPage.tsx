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
  FileText,
  ExternalLink,
  Plus,
  Trash2
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

  // Edit form states for all 9 fields
  const [editName, setEditName] = useState('')
  const [editPhoto, setEditPhoto] = useState('')
  const [editShortDesc, setEditShortDesc] = useState('')
  const [editLongDesc, setEditLongDesc] = useState('')
  const [editInclusions, setEditInclusions] = useState('')
  const [editFaqs, setEditFaqs] = useState<{ question: string; answer: string }[]>([])
  const [editNote, setEditNote] = useState('')
  const [editKeywords, setEditKeywords] = useState('')
  const [editTags, setEditTags] = useState('')
  const [customFields, setCustomFields] = useState<{ key: string; value: string }[]>([])

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

  const regenerateMutation = useMutation({
    mutationFn: (imageId: number) => api.regenerateMetadata(imageId),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['all-metadata'] })
      alert(`Regenerated AI metadata for '${updated.name}'.`)
      if (selectedMeta && selectedMeta.id === updated.id) {
        setSelectedMeta(updated)
      }
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Regeneration failed')
    },
  })

  const exportSheetsMutation = useMutation({
    mutationFn: () => api.exportToGoogleSheets(undefined, 'APPROVED'),
    onSuccess: (res) => {
      alert(`Published ${res.total_rows} items to Google Sheets!\nSheet URL: ${res.sheet_url}`)
      if (res.sheet_url) {
        window.open(res.sheet_url, '_blank')
      }
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Google Sheets export failed')
    },
  })

  const updateMetaMutation = useMutation({
    mutationFn: (payload: { id: number; data: Partial<ImageMetadata> }) =>
      api.updateMetadata(payload.id, payload.data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['all-metadata'] })
      setSelectedMeta(updated)
      setEditModalOpen(false)
      alert('Metadata updated successfully.')
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Update failed')
    },
  })

  const handleOpenEdit = (meta: ImageMetadata) => {
    setSelectedMeta(meta)
    setEditName(meta.name)
    setEditPhoto(meta.photo || meta.image_url || '')
    setEditShortDesc(meta.short_description)
    setEditLongDesc(meta.long_description)
    setEditInclusions((meta.inclusion || []).join('\n'))
    setEditFaqs(meta.faq || [])
    setEditNote(meta.note || '')
    setEditKeywords((meta.keywords || []).join(', '))
    setEditTags((meta.tags || []).join(', '))

    const cfList: { key: string; value: string }[] = []
    if (meta.custom_fields && typeof meta.custom_fields === 'object') {
      for (const [k, v] of Object.entries(meta.custom_fields)) {
        cfList.push({ key: k, value: String(v) })
      }
    }
    setCustomFields(cfList)

    setEditModalOpen(true)
  }

  const handleAddFaq = () => {
    setEditFaqs((prev) => [...prev, { question: '', answer: '' }])
  }

  const handleRemoveFaq = (index: number) => {
    setEditFaqs((prev) => prev.filter((_, i) => i !== index))
  }

  const handleAddCustomField = () => {
    setCustomFields((prev) => [...prev, { key: '', value: '' }])
  }

  const handleRemoveCustomField = (index: number) => {
    setCustomFields((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedMeta) return

    const incArray = editInclusions
      .split('\n')
      .map((i) => i.trim())
      .filter(Boolean)

    const kwArray = editKeywords
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean)

    const tagArray = editTags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    const cfObj: Record<string, string> = {}
    for (const item of customFields) {
      if (item.key.trim()) {
        cfObj[item.key.trim()] = item.value.trim()
      }
    }

    updateMetaMutation.mutate({
      id: selectedMeta.id,
      data: {
        name: editName,
        short_description: editShortDesc,
        long_description: editLongDesc,
        inclusion: incArray,
        faq: editFaqs.filter((f) => f.question.trim()),
        note: editNote,
        keywords: kwArray,
        tags: tagArray,
        custom_fields: cfObj,
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
            Enterprise copywriting engine for approved decoration photographs. Generates complete 9-field structured metadata with zero price hallucination.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            size="sm"
            onClick={() => bulkGenerateMutation.mutate()}
            isLoading={bulkGenerateMutation.isPending}
            className="gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Bulk Generate Approved
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => exportSheetsMutation.mutate()}
            isLoading={exportSheetsMutation.isPending}
            className="gap-2"
          >
            <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
            Export to Google Sheets
          </Button>
          <a href="/api/v1/reports/export?format=excel&status=APPROVED" download>
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="w-4 h-4" />
              Download Excel
            </Button>
          </a>
        </div>
      </div>

      {/* Main Grid */}
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
                  <div className="truncate pr-2">
                    <span className="font-semibold text-xs text-slate-800 truncate block">
                      {meta.name}
                    </span>
                    <span className="text-[10px] text-slate-400 truncate block">
                      Category: {meta.category_name || 'Unassigned'} • Photo: {meta.original_filename || `#${meta.image_id}`}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => regenerateMutation.mutate(meta.image_id)}
                      isLoading={regenerateMutation.isPending}
                      className="p-1 h-7"
                      title="Regenerate with AI"
                    >
                      <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleOpenEdit(meta)} className="p-1 h-7" title="Edit Metadata">
                      <Edit2 className="w-3.5 h-3.5 text-slate-600" />
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="p-4 space-y-3 text-xs">
                  {/* Image preview thumbnail */}
                  {meta.image_url && (
                    <div className="h-36 bg-slate-100 rounded-lg overflow-hidden relative group">
                      <img
                        src={meta.image_url}
                        alt={meta.name}
                        className="w-full h-full object-cover"
                      />
                      {meta.photo && (
                        <a
                          href={meta.photo}
                          target="_blank"
                          rel="noreferrer"
                          className="absolute bottom-2 right-2 bg-black/70 hover:bg-black/90 text-white text-[10px] px-2 py-1 rounded flex items-center gap-1 shadow"
                        >
                          <ExternalLink className="w-3 h-3" /> Full Asset
                        </a>
                      )}
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
                        Visible Inclusions ({meta.inclusion.length})
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
                  View Full 9 Fields & Edit →
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

      {/* Full 9-Field & Custom Fields Edit Specs Modal */}
      {selectedMeta && (
        <Modal
          isOpen={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          title={`Edit Product Specs: ${selectedMeta.name}`}
          maxWidth="4xl"
        >
          <form onSubmit={handleSaveEdit} className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
            {/* System Specs Header */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 bg-slate-50 rounded-xl text-slate-600 text-[11px] border">
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Image ID</span>
                <strong className="text-slate-800">#{selectedMeta.image_id}</strong>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Category</span>
                <strong className="text-slate-800">{selectedMeta.category_name || 'Unassigned'}</strong>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Filename</span>
                <strong className="text-slate-800 truncate block">{selectedMeta.original_filename}</strong>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Approval Status</span>
                <Badge variant="approved">APPROVED</Badge>
              </div>
            </div>

            {/* 1. Name */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">1. Product Title / Name *</label>
              <input
                type="text"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* 2. Photo URL */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">2. Photo URL (Google Drive or Asset Path)</label>
              <input
                type="text"
                value={editPhoto}
                onChange={(e) => setEditPhoto(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono text-slate-700 focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* 3. Short Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">3. Short Description *</label>
              <textarea
                rows={2}
                required
                value={editShortDesc}
                onChange={(e) => setEditShortDesc(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* 4. Long Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">4. Long Description *</label>
              <textarea
                rows={4}
                required
                value={editLongDesc}
                onChange={(e) => setEditLongDesc(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* 5. Inclusions */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">5. Inclusions (One per line)</label>
              <textarea
                rows={3}
                value={editInclusions}
                onChange={(e) => setEditInclusions(e.target.value)}
                placeholder="Circular metal backdrop arch&#10;Organic balloon clusters&#10;On-site setup & tear-down"
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* 6. FAQs */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-700">6. FAQs (Question & Answer)</label>
                <button
                  type="button"
                  onClick={handleAddFaq}
                  className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" /> Add FAQ
                </button>
              </div>
              <div className="space-y-2">
                {editFaqs.map((faq, index) => (
                  <div key={index} className="p-2.5 bg-slate-50 border rounded-lg space-y-1.5 relative">
                    <button
                      type="button"
                      onClick={() => handleRemoveFaq(index)}
                      className="absolute top-2 right-2 text-slate-400 hover:text-rose-600"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <input
                      type="text"
                      placeholder="Question: e.g. Can this be set up outdoors?"
                      value={faq.question}
                      onChange={(e) => {
                        const copy = [...editFaqs]
                        copy[index].question = e.target.value
                        setEditFaqs(copy)
                      }}
                      className="w-full px-2.5 py-1.5 bg-white border rounded text-xs"
                    />
                    <input
                      type="text"
                      placeholder="Answer: e.g. Yes, with proper weather anchoring."
                      value={faq.answer}
                      onChange={(e) => {
                        const copy = [...editFaqs]
                        copy[index].answer = e.target.value
                        setEditFaqs(copy)
                      }}
                      className="w-full px-2.5 py-1.5 bg-white border rounded text-xs"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* 7. Note */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">7. Operational Logistics Note</label>
              <input
                type="text"
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
                placeholder="e.g. Requires 10x10ft cleared space."
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* 8. Keywords & 9. Tags */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">8. Keywords (Comma-separated)</label>
                <input
                  type="text"
                  value={editKeywords}
                  onChange={(e) => setEditKeywords(e.target.value)}
                  placeholder="wedding decor, stage setup, floral arch"
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">9. Tags (Comma-separated)</label>
                <input
                  type="text"
                  value={editTags}
                  onChange={(e) => setEditTags(e.target.value)}
                  placeholder="Wedding, Floral, Grand Stage"
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Dynamic Custom Fields */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-700">Dynamic Custom Fields</label>
                <button
                  type="button"
                  onClick={handleAddCustomField}
                  className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Field
                </button>
              </div>
              <div className="space-y-2">
                {customFields.map((cf, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Field Name (e.g. Color Palette)"
                      value={cf.key}
                      onChange={(e) => {
                        const copy = [...customFields]
                        copy[idx].key = e.target.value
                        setCustomFields(copy)
                      }}
                      className="w-1/3 px-2.5 py-1.5 bg-white border rounded-lg text-xs"
                    />
                    <input
                      type="text"
                      placeholder="Value (e.g. Gold & Emerald Green)"
                      value={cf.value}
                      onChange={(e) => {
                        const copy = [...customFields]
                        copy[idx].value = e.target.value
                        setCustomFields(copy)
                      }}
                      className="flex-1 px-2.5 py-1.5 bg-white border rounded-lg text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => handleRemoveCustomField(idx)}
                      className="p-1.5 text-slate-400 hover:text-rose-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-4 border-t">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => regenerateMutation.mutate(selectedMeta.image_id)}
                isLoading={regenerateMutation.isPending}
                className="gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Regenerate with AI
              </Button>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setEditModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" isLoading={updateMetaMutation.isPending}>
                  Save All 9 Fields
                </Button>
              </div>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
