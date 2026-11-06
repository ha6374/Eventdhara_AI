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
  if (envBase && /^https?:\/\//i.test(envBase)) {
    try {
      return new URL(envBase).origin;
    } catch {
      // fallback
    }
  }
  if (import.meta.env.PROD) {
    return 'https://eventdhara-ai.onrender.com';
  }
  return typeof window !== 'undefined' ? window.location.origin : '';
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
} | null): string {
  if (!item) return '';

  // Priority 1: Google Drive URL if synced to cloud
  if (item.drive_url) return item.drive_url;
  if (item.drive_file_id) {
    return `https://drive.google.com/thumbnail?id=${item.drive_file_id}&sz=w1200`;
  }

  // Priority 2: Dedicated image serving API endpoint
  if (item.id) {
    const backendOrigin = getBackendOrigin();
    return `${backendOrigin}/api/v1/images/${item.id}/file`;
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
