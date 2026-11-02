import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Image as ImageIcon,
  CheckCircle2,
  XCircle,
  Clock,
  CopyCheck,
  FileSpreadsheet,
  Cloud,
  TrendingUp,
  Activity,
  ArrowUpRight,
  Sparkles,
  UploadCloud,
  Gauge,
  CheckCircle,
  AlertCircle
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts'
import { api } from '@/services/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatDate } from '@/lib/utils'

const PIE_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#6366F1', '#14B8A6']

export const DashboardPage: React.FC = () => {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: () => api.getDashboardOverview(),
    refetchInterval: 10000, // Real-time poll every 10s
  })

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] gap-3">
        <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-slate-500 font-medium">Loading real-time PostgreSQL operational metrics...</span>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-rose-800">
        <h3 className="font-semibold text-sm">Failed to connect to backend service</h3>
        <p className="text-xs mt-1 text-rose-600">Please ensure the FastAPI backend is running and PostgreSQL is connected.</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
          Retry Connection
        </Button>
      </div>
    )
  }

  const { stats, daily_volume, category_distribution, quality_distribution, processing_performance, recent_activity } = data

  const statCards = [
    { title: 'Total Images', value: stats.total_images, icon: ImageIcon, color: 'text-slate-700', bg: 'bg-slate-100', link: '/galleries/approved' },
    { title: 'Approved', value: stats.approved, icon: CheckCircle2, color: 'text-emerald-700', bg: 'bg-emerald-50', link: '/galleries/approved' },
    { title: 'Review Required', value: stats.review_required, icon: Clock, color: 'text-amber-700', bg: 'bg-amber-50', link: '/galleries/review' },
    { title: 'Rejected', value: stats.rejected, icon: XCircle, color: 'text-rose-700', bg: 'bg-rose-50', link: '/galleries/rejected' },
    { title: 'Duplicates', value: stats.duplicates, icon: CopyCheck, color: 'text-purple-700', bg: 'bg-purple-50', link: '/duplicates' },
    { title: 'Metadata Completed', value: stats.metadata_completed, icon: FileSpreadsheet, color: 'text-blue-700', bg: 'bg-blue-50', link: '/metadata' },
    { title: 'Pending Metadata', value: stats.pending_metadata, icon: AlertCircle, color: 'text-indigo-700', bg: 'bg-indigo-50', link: '/metadata' },
    { title: 'Drive Uploads', value: stats.drive_uploads, icon: Cloud, color: 'text-cyan-700', bg: 'bg-cyan-50', link: '/google-drive' },
  ]

  const statusVariantMap = {
    APPROVED: 'approved',
    REJECTED: 'rejected',
    REVIEW_REQUIRED: 'review',
    DUPLICATE: 'duplicate',
    PENDING: 'pending',
  } as const

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            Operations Overview
            <span className="text-xs font-normal text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
              Live PostgreSQL Metrics
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time pipeline monitoring, automated quality scoring, and catalog ingestion telemetry.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/uploads">
            <Button size="sm" className="gap-2">
              <UploadCloud className="w-4 h-4" />
              Upload Photos
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Refresh Live Data
          </Button>
        </div>
      </div>

      {/* 8 Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <Link key={card.title} to={card.link}>
              <Card className="hover:border-slate-300 transition-all hover:shadow-xs group cursor-pointer">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-medium text-slate-500">{card.title}</span>
                    <div className="text-2xl font-bold text-slate-900 mt-1">{card.value.toLocaleString()}</div>
                  </div>
                  <div className={`p-2.5 rounded-xl ${card.bg} ${card.color} group-hover:scale-110 transition-transform`}>
                    <Icon className="w-5 h-5" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* Performance & Quality Telemetry Banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Processing Performance */}
        <Card className="bg-gradient-to-br from-slate-900 to-slate-800 text-white border-0 shadow-md">
          <CardContent className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <Gauge className="w-4 h-4 text-blue-400" />
                Pipeline Engine Latency
              </div>
              <div className="text-2xl font-bold tracking-tight">
                {processing_performance.average_duration_ms > 0
                  ? `${processing_performance.average_duration_ms} ms`
                  : 'Sub-millisecond'}
              </div>
              <p className="text-[11px] text-slate-400">
                Fastest: {processing_performance.fastest_duration_ms}ms • Slowest: {processing_performance.slowest_duration_ms}ms
              </p>
            </div>
            <div className="h-12 w-12 rounded-xl bg-white/10 flex items-center justify-center text-blue-400">
              <Activity className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>

        {/* Quality Check Distribution */}
        <Card className="border-slate-200">
          <CardContent className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                <CheckCircle className="w-4 h-4 text-emerald-600" />
                Automated Quality Score Pass Rate
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {quality_distribution.passed + quality_distribution.failed > 0
                  ? `${Math.round((quality_distribution.passed / (quality_distribution.passed + quality_distribution.failed)) * 100)}%`
                  : '100%'}
              </div>
              <p className="text-[11px] text-slate-500">
                Avg Laplacian Blur Score: {quality_distribution.average_blur_score} • {quality_distribution.passed} Passed, {quality_distribution.failed} Failed
              </p>
            </div>
            <div className="h-12 w-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Sparkles className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily Processing Volume (Bar Chart) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Daily Processing Volume & Trends</CardTitle>
              <CardDescription>Multi-day breakdown of approved, rejected, and review-required images</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily_volume} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748B' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748B' }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0F172A', borderRadius: '8px', border: 'none', color: '#fff', fontSize: '12px' }}
                  />
                  <Bar dataKey="approved" name="Approved" fill="#10B981" radius={[4, 4, 0, 0]} stackId="a" />
                  <Bar dataKey="review_required" name="Review Required" fill="#F59E0B" radius={[0, 0, 0, 0]} stackId="a" />
                  <Bar dataKey="rejected" name="Rejected" fill="#F43F5E" radius={[0, 0, 0, 0]} stackId="a" />
                  <Bar dataKey="duplicates" name="Duplicates" fill="#8B5CF6" radius={[4, 4, 0, 0]} stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Category Distribution (Donut / Pie Chart) */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Category Distribution</CardTitle>
              <CardDescription>Decoration inventory proportion by theme</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {category_distribution.length > 0 ? (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={category_distribution}
                      dataKey="count"
                      nameKey="category_name"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                    >
                      {category_distribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0F172A', borderRadius: '8px', border: 'none', color: '#fff', fontSize: '12px' }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex flex-col items-center justify-center text-center p-4">
                <ImageIcon className="w-8 h-8 text-slate-300 mb-2" />
                <span className="text-xs font-medium text-slate-600">No categorized images yet</span>
                <p className="text-[11px] text-slate-400 mt-1 max-w-[200px]">
                  Upload decoration photographs to view live category proportions.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Recent Activity Stream</CardTitle>
            <CardDescription>Live telemetry of most recently processed decoration photos</CardDescription>
          </div>
          <Link to="/galleries/approved">
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              View All <ArrowUpRight className="w-3.5 h-3.5" />
            </Button>
          </Link>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                <th className="py-3 px-6">Filename</th>
                <th className="py-3 px-6">Category</th>
                <th className="py-3 px-6">Status</th>
                <th className="py-3 px-6">Quality</th>
                <th className="py-3 px-6">Date</th>
                <th className="py-3 px-6 text-right">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recent_activity.length > 0 ? (
                recent_activity.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3.5 px-6 font-medium text-slate-800 flex items-center gap-2">
                      <ImageIcon className="w-4 h-4 text-slate-400" />
                      <span className="truncate max-w-[220px]">{item.filename}</span>
                    </td>
                    <td className="py-3.5 px-6 text-slate-600 font-medium">
                      {item.category}
                    </td>
                    <td className="py-3.5 px-6">
                      <Badge variant={statusVariantMap[item.status] || 'neutral'} dot>
                        {item.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-6">
                      <span className={`inline-flex items-center text-[11px] font-semibold ${item.quality_status === 'PASSED' ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {item.quality_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-6 text-slate-500">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="py-3.5 px-6 text-right font-mono text-slate-500 text-[11px]">
                      {item.processing_duration_ms ? `${Math.round(item.processing_duration_ms)}ms` : '—'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Activity className="w-6 h-6 text-slate-300" />
                      <p className="font-medium text-slate-600">No activity recorded yet</p>
                      <p className="text-[11px] text-slate-400">
                        Upload single images or ZIP files in the Upload Center to start automated pipeline processing.
                      </p>
                      <Link to="/uploads" className="mt-2">
                        <Button size="sm">Go to Upload Center</Button>
                      </Link>
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
