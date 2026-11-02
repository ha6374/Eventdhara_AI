import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  UploadCloud,
  Cpu,
  FolderTree,
  CheckCircle2,
  Clock,
  XCircle,
  CopyCheck,
  FileSpreadsheet,
  Cloud,
  BarChart3,
  FileText,
  Settings,
  Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  name: string
  to: string
  icon: React.ElementType
  badge?: string | number
}

const navItems: NavItem[] = [
  { name: 'Overview', to: '/', icon: LayoutDashboard },
  { name: 'Upload Center', to: '/uploads', icon: UploadCloud },
  { name: 'Processing Queue', to: '/processing', icon: Cpu },
  { name: 'Category Management', to: '/categories', icon: FolderTree },
  { name: 'Approved Gallery', to: '/galleries/approved', icon: CheckCircle2 },
  { name: 'Review Queue', to: '/galleries/review', icon: Clock },
  { name: 'Rejected Images', to: '/galleries/rejected', icon: XCircle },
  { name: 'Duplicate Center', to: '/duplicates', icon: CopyCheck },
  { name: 'Metadata Studio', to: '/metadata', icon: FileSpreadsheet },
  { name: 'Google Drive', to: '/google-drive', icon: Cloud },
  { name: 'Analytics', to: '/analytics', icon: BarChart3 },
  { name: 'Reports', to: '/reports', icon: FileText },
  { name: 'Settings', to: '/settings', icon: Settings },
]

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-[#0b1329] text-slate-300 flex flex-col shrink-0 border-r border-[#1e293b] select-none h-screen sticky top-0">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-[#1e293b]">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-white text-sm tracking-tight flex items-center gap-1.5">
            EventDhara <span className="text-[10px] uppercase font-semibold tracking-wider text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20">AI</span>
          </span>
          <span className="text-[11px] text-slate-400">Data Operations Platform</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold tracking-wider uppercase text-slate-400">
          Core Operations
        </div>
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all group',
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30 font-semibold'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
              <span className="truncate">{item.name}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* Enterprise Status Footer */}
      <div className="p-4 border-t border-[#1e293b] bg-[#070c1a]">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <div className="flex flex-col text-[11px]">
            <span className="text-slate-300 font-medium">PostgreSQL Engine</span>
            <span className="text-slate-400 text-[10px]">Operational • v1.0 Enterprise</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
