import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

export function formatDate(dateString?: string | null) {
  if (!dateString) return '—'
  const d = new Date(dateString)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function getImageUrl(path?: string | null): string {
  if (!path) return '';

  // Preserve external image URLs
  if (/^https?:\/\//i.test(path)) return path;

  const cleanPath = path.replace(/^\/+/, '');
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.PROD
      ? 'https://eventdhara-ai.onrender.com/api/v1'
      : '');

  if (apiBaseUrl) {
    const backendOrigin = new URL(apiBaseUrl).origin;
    return `${backendOrigin}/${cleanPath}`;
  }

  return `/${cleanPath}`;
}
