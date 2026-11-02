import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FolderTree,
  Plus,
  Search,
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Edit2,
  Trash2,
  Sparkles,
  Layers,
  CheckCircle,
  XCircle,
  Image as ImageIcon
} from 'lucide-react'
import { api } from '@/services/api'
import type { CategoryTreeNode } from '@/types'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Badge } from '@/components/ui/Badge'

export const CategoryPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [expandedNodes, setExpandedNodes] = useState<Record<number, boolean>>({})

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<'create_root' | 'create_sub' | 'edit'>('create_root')
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formParentId, setFormParentId] = useState<number | null>(null)
  const [formActive, setFormActive] = useState(true)

  const { data: tree = [], isLoading } = useQuery({
    queryKey: ['category-tree'],
    queryFn: () => api.getCategoryTree(),
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string; parent_id?: number | null }) =>
      api.createCategory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['category-tree'] })
      setIsModalOpen(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: { id: number; name?: string; description?: string; is_active?: boolean }) =>
      api.updateCategory(data.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['category-tree'] })
      setIsModalOpen(false)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteCategory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['category-tree'] })
      if (selectedCategoryId) setSelectedCategoryId(null)
    },
  })

  const seedMutation = useMutation({
    mutationFn: () => api.seedCategories(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['category-tree'] })
    },
  })

  const resetForm = () => {
    setFormName('')
    setFormDescription('')
    setFormParentId(null)
    setFormActive(true)
  }

  const toggleExpand = (id: number) => {
    setExpandedNodes((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  // Find node by id in tree
  const findNode = (nodes: CategoryTreeNode[], id: number): CategoryTreeNode | null => {
    for (const node of nodes) {
      if (node.id === id) return node
      if (node.children?.length) {
        const found = findNode(node.children, id)
        if (found) return found
      }
    }
    return null
  }

  const selectedNode = selectedCategoryId ? findNode(tree, selectedCategoryId) : (tree[0] || null)

  const handleOpenCreateRoot = () => {
    resetForm()
    setModalMode('create_root')
    setIsModalOpen(true)
  }

  const handleOpenCreateSub = (parentId: number) => {
    resetForm()
    setFormParentId(parentId)
    setModalMode('create_sub')
    setIsModalOpen(true)
  }

  const handleOpenEdit = (node: CategoryTreeNode) => {
    setFormName(node.name)
    setFormDescription(node.description || '')
    setFormActive(node.is_active)
    setFormParentId(node.parent_id || null)
    setModalMode('edit')
    setIsModalOpen(true)
  }

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formName.trim()) return

    if (modalMode === 'edit' && selectedNode) {
      updateMutation.mutate({
        id: selectedNode.id,
        name: formName,
        description: formDescription,
        is_active: formActive,
      })
    } else {
      createMutation.mutate({
        name: formName,
        description: formDescription,
        parent_id: modalMode === 'create_sub' ? formParentId : null,
      })
    }
  }

  // Tree Node Component
  const TreeNodeItem: React.FC<{ node: CategoryTreeNode }> = ({ node }) => {
    const isExpanded = expandedNodes[node.id] ?? true
    const hasChildren = node.children && node.children.length > 0
    const isSelected = (selectedCategoryId || (tree[0] ? tree[0].id : null)) === node.id

    if (search && !node.name.toLowerCase().includes(search.toLowerCase()) && !hasChildren) {
      return null
    }

    return (
      <div className="select-none">
        <div
          onClick={() => setSelectedCategoryId(node.id)}
          className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors group ${
            isSelected
              ? 'bg-blue-50 text-blue-700 font-semibold border border-blue-200/60'
              : 'text-slate-700 hover:bg-slate-100'
          }`}
          style={{ paddingLeft: `${node.depth * 14 + 10}px` }}
        >
          <div className="flex items-center gap-2 truncate">
            {hasChildren ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  toggleExpand(node.id)
                }}
                className="text-slate-400 hover:text-slate-600 p-0.5"
              >
                {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            ) : (
              <span className="w-3.5 h-3.5" />
            )}
            {hasChildren ? (
              isExpanded ? (
                <FolderOpen className="w-4 h-4 text-blue-500 shrink-0" />
              ) : (
                <Folder className="w-4 h-4 text-amber-500 shrink-0" />
              )
            ) : (
              <Layers className="w-4 h-4 text-slate-400 shrink-0" />
            )}
            <span className="truncate">{node.name}</span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0 opacity-80 group-hover:opacity-100">
            <span className="text-[10px] bg-slate-200/70 text-slate-600 px-1.5 py-0.5 rounded-full font-mono">
              {node.image_count}
            </span>
          </div>
        </div>

        {hasChildren && isExpanded && (
          <div className="space-y-0.5 mt-0.5">
            {node.children.map((child) => (
              <TreeNodeItem key={child.id} node={child} />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Category Management
            <Badge variant="neutral">{tree.length} Root Categories</Badge>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Unlimited-depth taxonomy tree for decoration themes, subthemes, and catalog organization.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => seedMutation.mutate()} isLoading={seedMutation.isPending}>
            <Sparkles className="w-3.5 h-3.5 mr-1" />
            Sync Canonical Taxonomy
          </Button>
          <Button size="sm" onClick={handleOpenCreateRoot}>
            <Plus className="w-4 h-4 mr-1" />
            New Root Category
          </Button>
        </div>
      </div>

      {/* Split Panel Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* Left Panel: Category Tree */}
        <Card className="lg:col-span-5 flex flex-col h-full">
          <CardHeader className="p-4 border-b">
            <div className="w-full space-y-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">Taxonomy Tree</CardTitle>
                <span className="text-[11px] text-slate-400">Click to inspect</span>
              </div>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter categories..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-3 flex-1 overflow-y-auto max-h-[550px]">
            {isLoading ? (
              <div className="flex items-center justify-center p-8 text-xs text-slate-400">
                Loading categories...
              </div>
            ) : tree.length > 0 ? (
              <div className="space-y-1">
                {tree.map((node) => (
                  <TreeNodeItem key={node.id} node={node} />
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                No categories found. Click "Sync Canonical Taxonomy" above.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Panel: Category Details and Management */}
        <Card className="lg:col-span-7 flex flex-col">
          {selectedNode ? (
            <div>
              <CardHeader className="p-6 border-b flex-row items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900">{selectedNode.name}</h2>
                    <Badge variant={selectedNode.is_active ? 'approved' : 'neutral'} dot>
                      {selectedNode.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">Slug: <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-700">{selectedNode.slug}</code></p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleOpenCreateSub(selectedNode.id)}>
                    <Plus className="w-3.5 h-3.5 mr-1" /> Add Subcategory
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleOpenEdit(selectedNode)}>
                    <Edit2 className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      if (confirm(`Are you sure you want to delete '${selectedNode.name}'?`)) {
                        deleteMutation.mutate(selectedNode.id)
                      }
                    }}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="p-6 space-y-6">
                {/* Description & Overview */}
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200/70">
                  <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider text-[10px]">Description</span>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                    {selectedNode.description || 'No dedicated description provided for this decoration taxonomy node.'}
                  </p>
                </div>

                {/* Subcategory Statistics */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <span className="text-[11px] text-slate-500 font-medium">Direct & Nested Images</span>
                    <div className="text-2xl font-bold text-slate-900 mt-1 flex items-center gap-2">
                      <ImageIcon className="w-5 h-5 text-blue-600" />
                      {selectedNode.image_count}
                    </div>
                  </div>
                  <div className="p-4 rounded-xl border border-slate-200 bg-white">
                    <span className="text-[11px] text-slate-500 font-medium">Direct Subcategories</span>
                    <div className="text-2xl font-bold text-slate-900 mt-1 flex items-center gap-2">
                      <FolderTree className="w-5 h-5 text-amber-500" />
                      {selectedNode.children?.length || 0}
                    </div>
                  </div>
                </div>

                {/* Children Subcategories List */}
                <div>
                  <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider mb-3">
                    Subcategories ({selectedNode.children?.length || 0})
                  </h3>
                  {selectedNode.children && selectedNode.children.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {selectedNode.children.map((child) => (
                        <div
                          key={child.id}
                          onClick={() => setSelectedCategoryId(child.id)}
                          className="p-3 border border-slate-200 rounded-lg hover:border-blue-400 hover:bg-blue-50/30 transition-all cursor-pointer flex items-center justify-between"
                        >
                          <div className="truncate">
                            <span className="text-xs font-semibold text-slate-800 block truncate">{child.name}</span>
                            <span className="text-[10px] text-slate-400 block truncate">{child.description || 'No description'}</span>
                          </div>
                          <Badge variant="neutral">{child.image_count} photos</Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 text-center border border-dashed border-slate-200 rounded-xl text-xs text-slate-400">
                      No nested subcategories under this node. Click "Add Subcategory" to create one.
                    </div>
                  )}
                </div>
              </CardContent>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-slate-400">
              <FolderTree className="w-10 h-10 text-slate-300 mb-2" />
              <span className="text-sm font-semibold text-slate-700">Select a category</span>
              <p className="text-xs text-slate-500 mt-1 max-w-sm">
                Choose any category from the taxonomy tree on the left to review nested statistics and manage settings.
              </p>
            </div>
          )}
        </Card>
      </div>

      {/* Create / Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={
          modalMode === 'edit'
            ? 'Edit Category'
            : modalMode === 'create_sub'
            ? `Add Subcategory to '${selectedNode?.name}'`
            : 'Create Root Category'
        }
      >
        <form onSubmit={handleFormSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Category Name *</label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Cocomelon Theme, Romantic Birthday"
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Description</label>
            <textarea
              rows={3}
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Styling and decoration notes..."
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="cat-active"
              checked={formActive}
              onChange={(e) => setFormActive(e.target.checked)}
              className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4"
            />
            <label htmlFor="cat-active" className="text-xs text-slate-700 font-medium">
              Category Active in Ingestion Pipeline
            </label>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" isLoading={createMutation.isPending || updateMutation.isPending}>
              {modalMode === 'edit' ? 'Save Changes' : 'Create Category'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
