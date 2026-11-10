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

export function getBackendOrigin(): string {
  const envBase = import.meta.env.VITE_API_BASE_URL;

  // Always use the configured backend origin in production.
  if (envBase && /^https?:\/\//i.test(envBase)) {
    try {
      return new URL(envBase).origin;
    } catch {
      console.warn("Invalid VITE_API_BASE_URL:", envBase);
    }
  }

  // Explicit production backend fallback.
  if (import.meta.env.PROD) {
    return "https://eventdhara-ai.onrender.com";
  }

  return "http://localhost:8000";
}

export function getImageUrl(path?: string | null): string {
  if (!path) return '';

  // Preserve external image URLs (e.g. Google Drive, Cloudinary, S3)
  if (/^https?:\/\//i.test(path)) return path;

  const cleanPath = path.replace(/^\/+/, '');
  const backendOrigin = getBackendOrigin();

  if (backendOrigin) {
    return `${backendOrigin}/${cleanPath}`;
  }

  return `/${cleanPath}`;
}

export function getReliableImageUrl(item?: {
  id?: number
  drive_url?: string | null
  drive_file_id?: string | null
  storage_path?: string | null
  file_url?: string | null
  status?: string | null
} | null): string {
  if (!item) return '';

  const backendOrigin = getBackendOrigin();

  // Priority 1: Dedicated authenticated streaming API endpoint by ID
  // Serves binary image directly for ALL statuses (APPROVED, REVIEW_REQUIRED, REJECTED, DUPLICATE, PENDING)
  // Backed by disk storage, PostgreSQL binary backup data, or authenticated Google Drive API
  if (item.id) {
    return `${backendOrigin}/api/v1/images/${item.id}/file`;
  }

  // Priority 2: Direct file_url from backend schema
  if (item.file_url) {
    if (/^https?:\/\//i.test(item.file_url)) return item.file_url;
    const cleanUrl = item.file_url.replace(/^\/+/, '');
    return `${backendOrigin}/${cleanUrl}`;
  }

  // Priority 3: Static storage path
  if (item.storage_path) {
    return getImageUrl(item.storage_path);
  }

  return '';
}

export function getPlaceholderImageUrl(imageId?: number): string {
  if (!imageId) return '';
  const backendOrigin = getBackendOrigin();
  return `${backendOrigin}/api/v1/images/${imageId}/placeholder`;
}
