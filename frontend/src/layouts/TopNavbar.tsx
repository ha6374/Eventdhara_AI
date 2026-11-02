import React from 'react'
import { useLocation, Link } from 'react-router-dom'
import {
  Search,
  Bell,
  Cpu,
  User,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react'

export const TopNavbar: React.FC = () => {
  const location = useLocation()

  // Generate breadcrumb items
  const pathSnippets = location.pathname.split('/').filter((i) => i)
  const breadcrumbs = [
    { label: 'EventDhara', to: '/' },
    ...pathSnippets.map((snippet, index) => {
      const url = `/${pathSnippets.slice(0, index + 1).join('/')}`
      const formatted = snippet.charAt(0).toUpperCase() + snippet.slice(1).replace('-', ' ')
      return { label: formatted, to: url }
    }),
  ]

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-xs text-slate-500">
        {breadcrumbs.map((crumb, idx) => {
          const isLast = idx === breadcrumbs.length - 1
          return (
            <React.Fragment key={crumb.to}>
              {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-300" />}
              {isLast ? (
                <span className="font-semibold text-slate-800">{crumb.label}</span>
              ) : (
                <Link to={crumb.to} className="hover:text-blue-600 transition-colors">
                  {crumb.label}
                </Link>
              )}
            </React.Fragment>
          )
        })}
      </nav>

      {/* Center / Right Section */}
      <div className="flex items-center gap-4">
        {/* Global Search */}
        <div className="relative w-64 hidden md:block">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search images, categories, tags..."
            className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white transition-all"
          />
        </div>

        {/* Processing Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-100 rounded-lg text-blue-700 text-xs font-medium">
          <Cpu className="w-3.5 h-3.5 text-blue-600 animate-spin" />
          <span className="hidden sm:inline">AI Pipeline:</span> Active
        </div>

        {/* Notification Bell */}
        <button
          className="relative p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-600 rounded-full" />
        </button>

        {/* User Profile */}
        <div className="flex items-center gap-3 pl-3 border-l border-slate-200">
          <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center font-medium text-xs shadow-xs">
            ED
          </div>
          <div className="flex flex-col hidden lg:flex">
            <span className="text-xs font-semibold text-slate-800 flex items-center gap-1">
              Data Operations Lead <ShieldCheck className="w-3 h-3 text-blue-600" />
            </span>
            <span className="text-[10px] text-slate-500">lead-ops@eventdhara.com</span>
          </div>
        </div>
      </div>
    </header>
  )
}
