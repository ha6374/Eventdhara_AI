
import React, { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  UploadCloud,
  FileArchive,
  Image as ImageIcon,
  CheckCircle2,
  X,
  Sparkles
} from 'lucide-react'

import { api } from '@/services/api'
import type { CategoryTreeNode, ImageItem } from '@/types'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent
} from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatBytes } from '@/lib/utils'

export const UploadPage: React.FC = () => {
  const queryClient = useQueryClient()

  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [uploadMode, setUploadMode] = useState<'images' | 'zip'>('images')
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  const [uploadStats, setUploadStats] = useState<{
    total: number
    accepted: number
    rejected: number
    review: number
    duplicates: number
    invalid: number
    message: string
    items: ImageItem[]
  } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: tree = [] } = useQuery({
    queryKey: ['category-tree'],
    queryFn: () => api.getCategoryTree(),
  })

  const flattenCategories = (
    nodes: CategoryTreeNode[],
    depth = 0
  ): { id: number; name: string }[] => {
    let result: { id: number; name: string }[] = []

    for (const node of nodes) {
      const prefix = depth > 0 ? `${'— '.repeat(depth)}` : ''

      result.push({
        id: node.id,
        name: `${prefix}${node.name}`
      })

      if (node.children?.length) {
        result = result.concat(
          flattenCategories(node.children, depth + 1)
        )
      }
    }

    return result
  }

  const categoryOptions = flattenCategories(tree)

  // Calculate actual image classification counts
  const createUploadStats = (data: any) => {
    const items: ImageItem[] = Array.isArray(data.processed_items)
      ? data.processed_items
      : []

    const accepted = items.filter(
      (item: any) => String(item.status).toUpperCase() === 'APPROVED'
    ).length

    const rejected = items.filter(
      (item: any) => String(item.status).toUpperCase() === 'REJECTED'
    ).length

    const review = items.filter(
      (item: any) => String(item.status).toUpperCase() === 'REVIEW_REQUIRED'
    ).length

    const duplicates = items.filter(
      (item: any) => String(item.status).toUpperCase() === 'DUPLICATE'
    ).length

    return {
      total: Number(data.total_received ?? items.length),
      accepted,
      rejected,
      review,
      duplicates,
      invalid: Number(data.invalid_files ?? 0),
      message: data.message ?? 'Upload processing completed.',
      items
    }
  }

  const handleUploadSuccess = (data: any) => {
    queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] })
    queryClient.invalidateQueries({ queryKey: ['category-tree'] })

    setUploadStats(createUploadStats(data))
    setSelectedFiles([])
    setUploadProgress(null)
  }

  const uploadImagesMutation = useMutation({
    mutationFn: (files: File[]) =>
      api.uploadImages(files, selectedCategoryId),

    onSuccess: handleUploadSuccess,

    onError: (err: any) => {
      setUploadProgress(null)
      alert(err.response?.data?.detail || 'Upload failed')
    },
  })

  const uploadZipMutation = useMutation({
    mutationFn: (file: File) =>
      api.uploadZip(file, selectedCategoryId),

    onSuccess: handleUploadSuccess,

    onError: (err: any) => {
      setUploadProgress(null)
      alert(err.response?.data?.detail || 'ZIP processing failed')
    },
  })

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(Array.from(e.dataTransfer.files))
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(Array.from(e.target.files))
    }

    e.target.value = ''
  }

  const addFiles = (files: File[]) => {
    if (uploadMode === 'zip') {
      const zipFile = files.find(
        (f) => f.name.toLowerCase().endsWith('.zip')
      )

      if (zipFile) {
        setSelectedFiles([zipFile])
      } else {
        alert('Please upload a .zip file in ZIP mode.')
      }
    } else {
      const imageFiles = files.filter(
        (f) => /\.(jpg|jpeg|png|webp)$/i.test(f.name)
      )

      setSelectedFiles((prev) => [...prev, ...imageFiles])
    }
  }

  const removeFile = (index: number) => {
    setSelectedFiles((prev) =>
      prev.filter((_, i) => i !== index)
    )
  }

  const handleStartUpload = () => {
    if (selectedFiles.length === 0) return

    setUploadStats(null)
    setUploadProgress(50)

    if (uploadMode === 'zip') {
      uploadZipMutation.mutate(selectedFiles[0])
    } else {
      uploadImagesMutation.mutate(selectedFiles)
    }
  }

  const isUploading =
    uploadImagesMutation.isPending ||
    uploadZipMutation.isPending

  return (
    <div className="space-y-6 max-w-7xl mx-auto">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Upload Center
        </h1>

        <p className="text-xs text-slate-500 mt-1">
          High-performance streaming upload engine with automated
          integrity check, duplicate hashing, and AI classification.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Main Upload Zone */}
        <div className="lg:col-span-2 space-y-6">

          <Card>
            <CardHeader className="p-4 border-b">
              <div className="flex items-center justify-between w-full">

                <div className="flex items-center gap-2">

                  <button
                    type="button"
                    onClick={() => {
                      setUploadMode('images')
                      setSelectedFiles([])
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      uploadMode === 'images'
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    Multiple / Single Images
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setUploadMode('zip')
                      setSelectedFiles([])
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      uploadMode === 'zip'
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    ZIP Streaming Archive
                  </button>

                </div>

                <span className="text-[11px] text-slate-400">
                  Up to 500MB per batch
                </span>

              </div>
            </CardHeader>

            <CardContent className="p-6">

              {/* Drag and Drop */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
                  dragActive
                    ? 'border-blue-500 bg-blue-50/50 scale-[0.99]'
                    : 'border-slate-200 hover:border-blue-400 hover:bg-slate-50/50'
                }`}
              >

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple={uploadMode === 'images'}
                  accept={
                    uploadMode === 'zip'
                      ? '.zip'
                      : 'image/jpeg,image/png,image/webp'
                  }
                  onChange={handleFileSelect}
                  className="hidden"
                />

                <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4 shadow-xs">
                  {uploadMode === 'zip'
                    ? <FileArchive className="w-6 h-6" />
                    : <UploadCloud className="w-6 h-6" />
                  }
                </div>

                <h3 className="text-sm font-semibold text-slate-800">
                  {uploadMode === 'zip'
                    ? 'Drop ZIP Archive here'
                    : 'Drop decoration images here'
                  }
                </h3>

                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                  {uploadMode === 'zip'
                    ? 'Supports massive archives. Files will be extracted using streaming decompression directly to disk.'
                    : 'Select one or hundreds of JPG, PNG, or WEBP photos to run through the AI pipeline.'
                  }
                </p>

                <div className="mt-4">
                  <Button size="sm" variant="outline" type="button">
                    Browse Local Storage
                  </Button>
                </div>

              </div>

              {/* Selected Files */}
              {selectedFiles.length > 0 && (
                <div className="mt-6 space-y-3">

                  <div className="flex items-center justify-between text-xs text-slate-600 font-semibold">
                    <span>
                      Selected Files ({selectedFiles.length})
                    </span>

                    <span>
                      Total Size:{' '}
                      {formatBytes(
                        selectedFiles.reduce(
                          (acc, f) => acc + f.size,
                          0
                        )
                      )}
                    </span>
                  </div>

                  <div className="max-h-56 overflow-y-auto space-y-2 border border-slate-200 rounded-xl p-3 bg-slate-50/50">

                    {selectedFiles.map((file, idx) => (
                      <div
                        key={`${file.name}-${idx}`}
                        className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200/80 text-xs"
                      >

                        <div className="flex items-center gap-2 truncate pr-2">

                          {uploadMode === 'zip' ? (
                            <FileArchive className="w-4 h-4 text-amber-500 shrink-0" />
                          ) : (
                            <ImageIcon className="w-4 h-4 text-blue-500 shrink-0" />
                          )}

                          <span className="font-medium text-slate-800 truncate">
                            {file.name}
                          </span>

                          <span className="text-[10px] text-slate-400 shrink-0 font-mono">
                            ({formatBytes(file.size)})
                          </span>

                        </div>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeFile(idx)
                          }}
                          className="text-slate-400 hover:text-rose-600 p-1 rounded"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>

                      </div>
                    ))}

                  </div>

                  {/* Upload Action */}
                  <div className="flex items-center justify-between pt-2">

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedFiles([])}
                      disabled={isUploading}
                    >
                      Clear Selection
                    </Button>

                    <Button
                      size="sm"
                      onClick={handleStartUpload}
                      isLoading={isUploading}
                      className="gap-2"
                    >
                      <Sparkles className="w-4 h-4" />
                      Start Pipeline ({selectedFiles.length}{' '}
                      {uploadMode === 'zip' ? 'Archive' : 'Photos'})
                    </Button>

                  </div>

                </div>
              )}

            </CardContent>
          </Card>

          {/* Upload Results */}
          {uploadStats && (
            <Card className="border-emerald-200 bg-emerald-50/30">

              <CardHeader className="p-4 border-b border-emerald-100 flex-row items-center justify-between">

                <div className="flex items-center gap-2 text-emerald-800 font-semibold text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  Pipeline Ingestion Finished
                </div>

                <Badge variant="approved">
                  {uploadStats.accepted} Accepted Photos
                </Badge>

              </CardHeader>

              <CardContent className="p-4 space-y-3">

                <p className="text-xs text-slate-700">
                  {uploadStats.message}
                </p>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-center">

                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">
                      Total Evaluated
                    </span>
                    <div className="text-lg font-bold text-slate-800 mt-0.5">
                      {uploadStats.total}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-emerald-200 text-emerald-700">
                    <span className="text-[10px] uppercase font-semibold">
                      Accepted
                    </span>
                    <div className="text-lg font-bold mt-0.5">
                      {uploadStats.accepted}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-rose-200 text-rose-700">
                    <span className="text-[10px] uppercase font-semibold">
                      Rejected
                    </span>
                    <div className="text-lg font-bold mt-0.5">
                      {uploadStats.rejected}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-amber-200 text-amber-700">
                    <span className="text-[10px] uppercase font-semibold">
                      Review Required
                    </span>
                    <div className="text-lg font-bold mt-0.5">
                      {uploadStats.review}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-purple-200 text-purple-700">
                    <span className="text-[10px] uppercase font-semibold">
                      Duplicates
                    </span>
                    <div className="text-lg font-bold mt-0.5">
                      {uploadStats.duplicates}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-lg border text-slate-600">
                    <span className="text-[10px] uppercase font-semibold">
                      Invalid Files
                    </span>
                    <div className="text-lg font-bold mt-0.5">
                      {uploadStats.invalid}
                    </div>
                  </div>

                </div>

              </CardContent>
            </Card>
          )}

        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">

          <Card>
            <CardHeader className="p-4 border-b">
              <CardTitle className="text-sm">
                Target Category Mapping
              </CardTitle>

              <CardDescription>
                Optional default assignment for this batch
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 space-y-4">

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Category / Subcategory
                </label>

                <select
                  value={selectedCategoryId || ''}
                  onChange={(e) =>
                    setSelectedCategoryId(
                      e.target.value ? Number(e.target.value) : null
                    )
                  }
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">
                    Auto-Detect via Gemini AI Vision
                  </option>

                  {categoryOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.name}
                    </option>
                  ))}

                </select>

                <p className="text-[11px] text-slate-500 mt-1.5">
                  If set, images will inherit this category unless Gemini Vision identifies a high-confidence subcategory match.
                </p>
              </div>

            </CardContent>
          </Card>

          <Card>
            <CardHeader className="p-4 border-b">
              <CardTitle className="text-sm">
                Active 5-Step Pipeline
              </CardTitle>
            </CardHeader>

            <CardContent className="p-4 space-y-3 text-xs">

              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  1
                </div>
                <div>
                  <span className="font-semibold text-slate-800">
                    File Validation
                  </span>
                  <p className="text-[11px] text-slate-500">
                    Integrity check, min 800x600 resolution, corrupt file filter.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  2
                </div>
                <div>
                  <span className="font-semibold text-slate-800">
                    Global Duplicate Hashing
                  </span>
                  <p className="text-[11px] text-slate-500">
                    SHA256 exact collisions and 64-bit pHash perceptual distance.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  3
                </div>
                <div>
                  <span className="font-semibold text-slate-800">
                    OpenCV Quality Check
                  </span>
                  <p className="text-[11px] text-slate-500">
                    Laplacian variance blur detection thresholding.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  4
                </div>
                <div>
                  <span className="font-semibold text-slate-800">
                    Gemini AI Classification
                  </span>
                  <p className="text-[11px] text-slate-500">
                    Event decoration taxonomy mapping with visual evidence.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 font-bold text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  5
                </div>
                <div>
                  <span className="font-semibold text-slate-800">
                    Final Policy Decision
                  </span>
                  <p className="text-[11px] text-slate-500">
                    Automatic sorting to Approved, Review, Duplicate, or Rejected.
                  </p>
                </div>
              </div>

            </CardContent>
          </Card>

        </div>
      </div>
    </div>
  )
}
