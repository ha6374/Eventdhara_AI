import React from 'react'
import { cn } from '@/lib/utils'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'approved' | 'rejected' | 'review' | 'duplicate' | 'pending' | 'neutral'
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  dot = false,
  className,
  ...props
}) => {
  const variants = {
    approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rejected: 'bg-rose-50 text-rose-700 border-rose-200',
    review: 'bg-amber-50 text-amber-700 border-amber-200',
    duplicate: 'bg-purple-50 text-purple-700 border-purple-200',
    pending: 'bg-blue-50 text-blue-700 border-blue-200',
    neutral: 'bg-slate-50 text-slate-600 border-slate-200',
  }

  const dotColors = {
    approved: 'bg-emerald-500',
    rejected: 'bg-rose-500',
    review: 'bg-amber-500',
    duplicate: 'bg-purple-500',
    pending: 'bg-blue-500',
    neutral: 'bg-slate-400',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border tracking-wide uppercase',
        variants[variant],
        className
      )}
      {...props}
    >
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', dotColors[variant])} />}
      {children}
    </span>
  )
}
