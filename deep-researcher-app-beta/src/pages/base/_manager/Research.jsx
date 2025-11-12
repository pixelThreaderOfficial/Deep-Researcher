import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BookOpen,
  Clock,
  FileText,
  Tag,
  Calendar,
  RefreshCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { fetchResearch } from '@/lib/researchApi'
import StreamingMessageView from '@/components/widgets/StreamingMessageView'

const Research = () => {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [research, setResearch] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchResearch(slug)
      setResearch(data)
    } catch (e) {
      setError(e?.message || 'Failed to load research')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (slug) load()
  }, [slug])

  // Format duration from milliseconds to mm:ss
  const formatDuration = (durationSec) => {
    if (!durationSec || durationSec <= 0) return '--:--'
    const totalSeconds = Math.floor(durationSec)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '—'
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Get status badge color
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'running':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      case 'failed':
        return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'queued':
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  // Helpers to detect and extract URLs for previews
  const isImageUrl = (url = '') => /\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(url)
  const extractUrlsFromString = (str = '') => {
    if (!str) return []
    const urlRegex = /(https?:\/\/[^\s)"'>]+)/g
    const matches = str.match(urlRegex)
    return matches ? matches : []
  }
  const extractYouTubeId = (url = '') => {
    try {
      const u = new URL(url)
      if (u.hostname.includes('youtu.be')) {
        return u.pathname.split('/')[1] || null
      }
      if (u.hostname.includes('youtube.com')) {
        if (u.pathname.startsWith('/watch')) return u.searchParams.get('v')
        if (u.pathname.startsWith('/embed/')) return u.pathname.split('/')[2]
        if (u.pathname.startsWith('/shorts/')) return u.pathname.split('/')[2]
      }
    } catch (e) {
      // ignore invalid URLs
    }
    return null
  }

  // Build image and YouTube collections from metadata, sources, and answer text
  const imageUrls = useMemo(() => {
    const set = new Set()
    // From metadata.images
    if (research?.metadata?.images && Array.isArray(research.metadata.images)) {
      research.metadata.images.forEach((img) => {
        const src = img?.file_url || img?.url
        if (src) set.add(src)
      })
    }
    // From resources_used
    // if (Array.isArray(research?.resources_used)) {
    //   research.resources_used.forEach((u) => {
    //     if (typeof u === 'string' && isImageUrl(u)) set.add(u)
    //   })
    // }
    // From answer text
    if (typeof research?.answer === 'string') {
      extractUrlsFromString(research.answer).forEach((u) => {
        if (isImageUrl(u)) set.add(u)
      })
    }
    return Array.from(set)
  }, [research])

  const youtubeVideos = useMemo(() => {
    const byId = new Map()
    // From metadata.youtube.videos
    const metaVideos = research?.metadata?.youtube?.videos
    if (Array.isArray(metaVideos)) {
      metaVideos.forEach((v) => {
        const id = v?.id || extractYouTubeId(v?.url)
        if (id && !byId.has(id)) byId.set(id, { id, title: v?.title || '', url: v?.url || '' })
      })
    }
    // From resources_used
    if (Array.isArray(research?.resources_used)) {
      research.resources_used.forEach((u) => {
        const id = typeof u === 'string' ? extractYouTubeId(u) : null
        if (id && !byId.has(id)) byId.set(id, { id, title: '', url: u })
      })
    }
    // From answer text
    if (typeof research?.answer === 'string') {
      extractUrlsFromString(research.answer).forEach((u) => {
        const id = extractYouTubeId(u)
        if (id && !byId.has(id)) byId.set(id, { id, title: '', url: u })
      })
    }
    return Array.from(byId.values())
  }, [research])

  const handleImageError = (e) => {
    if (e?.target) e.target.style.display = 'none'
  }

  const nonImageSources = useMemo(() => {
    if (!Array.isArray(research?.resources_used)) return []
    return research.resources_used.filter((u) => typeof u === 'string' && !isImageUrl(u))
  }, [research])

  return (
    <div className="p-6 space-y-6">
      {loading && (
        <div className="text-sm text-gray-400">Loading research…</div>
      )}
      {error && (
        <div className="text-sm text-red-400">{error}</div>
      )}
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-4"
      >
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/app/researches')}
            className="text-gray-400 hover:text-gray-200 p-2"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={load}
            disabled={loading}
            className="text-gray-300 gap-2"
            title="Reload"
          >
            <RefreshCcw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <motion.div
            whileHover={{ rotate: 180 }}
            transition={{ duration: 0.3 }}
          >
            <BookOpen className="w-6 h-6 text-blue-400" />
          </motion.div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-semibold text-gray-100">{research?.title || 'Research'}</h1>
              {research?.status && (
                <Badge className={`${getStatusColor(research.status)} text-xs`}>
                  {research.status.charAt(0).toUpperCase() + research.status.slice(1)}
                </Badge>
              )}
            </div>
            <p className="text-sm text-gray-400">Slug: {slug}</p>
          </div>
        </div>

        {/* Metadata Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-gray-400">Duration</span>
            </div>
            <div className="text-lg font-bold text-gray-200">
              {research ? formatDuration(research.durationSec ?? research.duration ?? 0) : '—'}
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-gray-400">Sources</span>
            </div>
            <div className="text-lg font-bold text-gray-200">
              {research?.resources_used?.length ?? 0}
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-gray-400">Created</span>
            </div>
            <div className="text-sm font-medium text-gray-200">
              {research ? formatDate(research.datetime_start) : '—'}
            </div>
          </div>

          <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-gray-400">Model</span>
            </div>
            <div className="text-sm font-bold text-gray-200">
              {research?.model || '—'}
            </div>
          </div>
        </div>

        {/* Tags */}
        {Array.isArray(research?.tags) && research.tags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap bg-gray-800 border border-gray-600 rounded-lg p-4">
            <Tag className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="text-sm text-gray-400">Tags:</span>
            {research.tags.map((tag, tagIndex) => (
              <Badge
                key={tagIndex}
                variant="outline"
                className="bg-gray-700/50 text-gray-300 border-gray-600"
              >
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </motion.div>

      {/* Image previews at top */}
      {imageUrls.length > 0 && (
        <div className="bg-gray-800 border border-gray-600 rounded-lg p-6 -mt-2">
          <h3 className="text-md font-semibold text-gray-300 mb-3">Image Previews</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {imageUrls.map((url, idx) => (
              <a key={idx} href={url} target="_blank" rel="noreferrer" className="group">
                <div className="relative bg-gray-900 border border-gray-700 rounded-md overflow-hidden">
                  <img
                    src={url}
                    alt=""
                    onError={handleImageError}
                    className="w-full h-32 object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* YouTube previews directly below images */}
      {youtubeVideos.length > 0 && (
        <div className="bg-gray-800 border border-gray-600 rounded-lg p-6 -mt-4">
          <h3 className="text-md font-semibold text-gray-300 mb-3">Video Previews</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {youtubeVideos.map((v) => (
              <div key={v.id} className="space-y-2">
                <div className="relative w-full overflow-hidden rounded-lg border border-gray-600 bg-black pt-[56.25%]">
                  <iframe
                    className="absolute inset-0 w-full h-full"
                    src={`https://www.youtube.com/embed/${v.id}?rel=0`}
                    title={v.title || 'YouTube video'}
                    frameBorder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allowFullScreen
                  />
                </div>
                {(v.title || v.url) && (
                  <div className="text-xs text-gray-400 truncate">
                    {v.title || v.url}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Content Placeholder */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
        className="bg-gray-800 border border-gray-600 rounded-lg p-6"
      >
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Research Content</h2>
        {research?.answer ? (
          <div className="max-w-none text-gray-200">
            <StreamingMessageView text={research.answer} />
          </div>
        ) : <p className="text-gray-400">No answer available yet.</p>}

        {/* Sources */}
        <div className="mt-6">
          <h3 className="text-md font-semibold text-gray-300 mb-2">Sources</h3>
          {nonImageSources && nonImageSources.length > 0 ? (
            <ul className="list-disc list-inside text-sm text-blue-300 space-y-1">
              {nonImageSources.map((src, i) => (
                <li key={i}>
                  <a href={src} target="_blank" rel="noreferrer" className="hover:underline">{src}</a>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-gray-500">No sources recorded.</div>
          )}
        </div>


        {/* Metadata summary */}
        {research?.metadata && (
          <div className="mt-6 text-sm text-gray-400">
            <div className='hidden'>Web results: {research.metadata.web_search_results_count ?? 0}</div>
            <div className='hidden' >RAG results: {research.metadata.rag_results_count ?? 0}</div>
          </div>
        )}
      </motion.div>
    </div>
  )
}

export default Research