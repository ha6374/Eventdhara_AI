import React, { useState, useEffect } from 'react'
import { ImageOff, AlertCircle } from 'lucide-react'
import { getBackendOrigin } from '@/lib/utils'

interface SafeImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  imageId?: number
  fallbackSrc?: string
  aspectRatio?: string
  showMissingBadge?: boolean
  containerClassName?: string
}

export const SafeImage: React.FC<SafeImageProps> = ({
  src,
  fallbackSrc,
  alt = 'Image',
  className = '',
  aspectRatio,
  imageId,
  showMissingBadge = true,
  containerClassName = '',
  onClick,
  ...props
}) => {
  const getInitialSrc = (): string | undefined => {
    if (src) return src
    if (imageId) return `${getBackendOrigin()}/api/v1/images/${imageId}/file`
    return fallbackSrc
  }

  const [currentSrc, setCurrentSrc] = useState<string | undefined>(getInitialSrc)
  const [hasError, setHasError] = useState(false)
  const [attemptedFallback, setAttemptedFallback] = useState(false)
  const [attemptedPlaceholder, setAttemptedPlaceholder] = useState(false)

  useEffect(() => {
    setCurrentSrc(getInitialSrc())
    setHasError(false)
    setAttemptedFallback(false)
    setAttemptedPlaceholder(false)
  }, [src, imageId, fallbackSrc])

  const handleError = () => {
    // 1. First retry: try fallbackSrc if available and different
    if (!attemptedFallback) {
      setAttemptedFallback(true)
      if (fallbackSrc && fallbackSrc !== currentSrc) {
        setCurrentSrc(fallbackSrc)
        return
      }
    }

    // 2. Second retry: try backend SVG placeholder endpoint
    if (!attemptedPlaceholder && imageId) {
      setAttemptedPlaceholder(true)
      const placeholderUrl = `${getBackendOrigin()}/api/v1/images/${imageId}/placeholder`
      if (placeholderUrl !== currentSrc) {
        setCurrentSrc(placeholderUrl)
        return
      }
    }

    setHasError(true)
  }

  if (hasError || !currentSrc) {
    return (
      <div
        onClick={onClick}
        className={`w-full h-full bg-slate-900 border border-slate-800 rounded-lg flex flex-col items-center justify-center p-4 text-center select-none overflow-hidden ${aspectRatio || ''} ${containerClassName}`}
        title={alt ? `Missing from server storage: ${alt}` : 'Asset missing from storage'}
      >
        <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-amber-400 mb-2 shadow-inner">
          <ImageOff className="w-5 h-5" />
        </div>
        <p className="text-xs font-semibold text-slate-200 truncate max-w-[90%]">
          {alt || 'Photo Missing'}
        </p>
        <p className="text-[11px] text-slate-400 mt-1 max-w-[85%]">
          Physical image file missing from server storage (404)
        </p>
        {showMissingBadge && (
          <div className="mt-2 flex items-center gap-1.5 bg-amber-950/70 text-amber-300 border border-amber-800/60 px-2.5 py-0.5 rounded-full text-[10px] font-medium">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="truncate">File Missing on Server</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <img
      src={currentSrc}
      alt={alt}
      onError={handleError}
      onClick={onClick}
      className={className}
      {...props}
    />
  )
}
