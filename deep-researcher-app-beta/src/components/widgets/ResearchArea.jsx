import React, { useState, useRef, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Paperclip, Send, Loader2, Copy, Volume2, RefreshCw, Sparkles, Image as ImageIcon, CheckCircle, AlertCircle } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../ui/dropdown-menu'
import { FileText, File } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import StreamingMessageView from './StreamingMessageView'
import ThinkingMarkdown from './ThinkingMarkdown'
import '../../md.css'

const ResearchArea = ({
    messages,
    onSend,
    isProcessing,
    researchProgress = '',
    researchSources = [],
    researchImages = [],
    researchNews = null,
    researchMetadata = null,
    initialInput = ''
}) => {
    const [input, setInput] = useState(initialInput || '')
    const [attachedFiles, setAttachedFiles] = useState([])
    const [isRecording, setIsRecording] = useState(false)
    const [isMultiline, setIsMultiline] = useState(false)
    const [isFileDropdownOpen, setIsFileDropdownOpen] = useState(false)
    const messagesContainerRef = useRef(null)
    const messageRefs = useRef(new Map())
    const textareaRef = useRef(null)
    const fileInputRef = useRef(null)
    const microphoneRef = useRef(null)
    const [isPinnedToBottom, setIsPinnedToBottom] = useState(true)
    const lastAlignedStreamIdRef = useRef(null)
    const lastUserAlignedRef = useRef(null)
    const prevMessagesCountRef = useRef(0)
    const pendingAlignUserToTopRef = useRef(false)

    // Floating research status panel state
    const [showResearchPanel, setShowResearchPanel] = useState(false)
    const [panelState, setPanelState] = useState('idle') // 'idle' | 'in-progress' | 'completed' | 'stopped'
    const prevIsProcessingRef = useRef(false)
    const panelTimerRef = useRef(null)

    const fileTypes = [
        { id: 'images', name: 'Images', icon: ImageIcon, description: 'PNG, JPG, GIF' },
        { id: 'pdfs', name: 'PDFs', icon: FileText, description: 'PDF files' },
        { id: 'documents', name: 'Documents', icon: FileText, description: 'DOC, DOCX, TXT' },
    ]

    // Keep view pinned to bottom while streaming/new messages, unless user scrolled up
    useEffect(() => {
        // Skip auto-pin scrolling while we're aligning user message to top
        if (pendingAlignUserToTopRef.current) return
        const el = messagesContainerRef.current
        if (!el) return
        if (isPinnedToBottom) {
            el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
        }
    }, [messages, isProcessing, isPinnedToBottom])

    // Track whether user is near the bottom to enable/disable pinning
    useEffect(() => {
        const el = messagesContainerRef.current
        if (!el) return

        const handleScroll = () => {
            const { scrollTop, scrollHeight, clientHeight } = el
            const isNearBottom = scrollHeight - scrollTop - clientHeight < 100
            setIsPinnedToBottom(isNearBottom)
        }

        el.addEventListener('scroll', handleScroll, { passive: true })
        return () => el.removeEventListener('scroll', handleScroll)
    }, [])

    // Auto-send initial input when component mounts with initialInput
    useEffect(() => {
        if (initialInput && initialInput.trim() && !isProcessing) {
            // Small delay to ensure component is fully mounted
            const timer = setTimeout(() => {
                handleSend()
            }, 100)
            return () => clearTimeout(timer)
        }
    }, [initialInput, isProcessing])

    // Manage floating research panel visibility and state
    useEffect(() => {
        // Clear any existing hide timers
        if (panelTimerRef.current) {
            clearTimeout(panelTimerRef.current)
            panelTimerRef.current = null
        }

        const wasProcessing = prevIsProcessingRef.current

        if (isProcessing) {
            setPanelState('in-progress')
            setShowResearchPanel(true)
        } else {
            if (researchMetadata) {
                // Completed successfully
                setPanelState('completed')
                setShowResearchPanel(true)
                panelTimerRef.current = setTimeout(() => setShowResearchPanel(false), 1800)
            } else if (wasProcessing) {
                // Terminated unexpectedly
                setPanelState('stopped')
                setShowResearchPanel(true)
                panelTimerRef.current = setTimeout(() => setShowResearchPanel(false), 1800)
            } else {
                setShowResearchPanel(false)
                setPanelState('idle')
            }
        }

        prevIsProcessingRef.current = isProcessing

        return () => {
            if (panelTimerRef.current) {
                clearTimeout(panelTimerRef.current)
                panelTimerRef.current = null
            }
        }
    }, [isProcessing, researchMetadata])

    const triggerFileInput = (type) => {
        if (fileInputRef.current) {
            fileInputRef.current.accept = getFileAcceptString(type)
            fileInputRef.current.click()
        }
    }

    const getFileAcceptString = (type) => {
        switch (type) {
            case 'Images':
                return 'image/*'
            case 'PDFs':
                return '.pdf'
            case 'Documents':
                return '.doc,.docx,.txt,.rtf'
            default:
                return '*'
        }
    }

    const handleFileSelect = (event) => {
        const files = Array.from(event.target.files)
        const newAttachments = files.map(file => ({
            file,
            importance: 'medium', // Default importance
            preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : null
        }))

        setAttachedFiles(prev => [...prev, ...newAttachments])

        // Reset file input
        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const removeAttachment = (index) => {
        setAttachedFiles(prev => {
            const newFiles = [...prev]
            const removed = newFiles.splice(index, 1)[0]
            // Clean up preview URL if it exists
            if (removed.preview) {
                URL.revokeObjectURL(removed.preview)
            }
            return newFiles
        })
    }

    const updateAttachmentImportance = (index, importance) => {
        setAttachedFiles(prev => prev.map((item, i) =>
            i === index ? { ...item, importance } : item
        ))
    }

    const handleSend = () => {
        if (input.trim() || attachedFiles.length > 0) {
            onSend(input.trim(), attachedFiles)
            setInput('')
            setAttachedFiles([])
        }
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            if (e.shiftKey || isMultiline) {
                // Shift+Enter or in multiline mode - allow new line
                return
            } else {
                // Enter - send message
                e.preventDefault()
                handleSend()
            }
        } else if (e.key === 'Escape') {
            // Escape - clear input
            setInput('')
            setAttachedFiles([])
        }
    }

    // Split into stable (non-streaming) messages and the current streaming assistant message (if any)
    const streamingIdx = useMemo(() => {
        if (!Array.isArray(messages)) return -1
        for (let i = messages.length - 1; i >= 0; i--) {
            const m = messages[i]
            // Only consider it streaming if it's explicitly true, not just truthy
            if (m && m.role === 'assistant' && m.streaming === true) return i
        }
        return -1
    }, [messages])

    const stableView = useMemo(() => {
        if (!Array.isArray(messages)) return []

        // Filter out the actively streaming message, but keep completed assistant messages
        if (streamingIdx >= 0) {
            return messages.filter((_, idx) => idx !== streamingIdx)
        }
        return messages
    }, [messages, streamingIdx])

    const stableKey = useMemo(() => {
        return stableView.map(m => m.id || `${m.role}-${m.createdAt}`).join(',')
    }, [stableView])

    // Determine the last non-streaming assistant message to attach images to
    const lastAssistantId = useMemo(() => {
        const arr = Array.isArray(stableView) ? stableView : []
        for (let i = arr.length - 1; i >= 0; i--) {
            const m = arr[i]
            if (m && m.role === 'assistant' && m.streaming !== true) return m.id
        }
        return null
    }, [stableView])

    // Helpers
    const getYouTubeId = (url) => {
        if (!url || typeof url !== 'string') return null
        try {
            const u = new URL(url)
            // youtu.be/<id>
            if (u.hostname.includes('youtu.be')) {
                const id = u.pathname.split('/').filter(Boolean)[0]
                return id || null
            }
            // youtube.com/watch?v=<id>
            if (u.searchParams.has('v')) return u.searchParams.get('v')
            // youtube.com/embed/<id>
            if (u.pathname.includes('/embed/')) {
                const parts = u.pathname.split('/embed/')
                if (parts[1]) return parts[1].split(/[?&]/)[0]
            }
            return null
        } catch {
            return null
        }
    }

    const buildEmbedUrl = (url) => {
        const id = getYouTubeId(url)
        if (!id) return null
        return `https://www.youtube-nocookie.com/embed/${id}`
    }

    const getReferenceGroups = (references) => {
        const refs = Array.isArray(references) ? references : []
        return {
            web: refs.filter(r => r?.type === 'web'),
            youtube: refs.filter(r => r?.type === 'youtube'),
            news: refs.filter(r => r?.type === 'news')
        }
    }

    return (
        <div className="flex-1 min-h-0 flex flex-col relative">
            {/* Floating research status (bottom-center above composer) */}
            <AnimatePresence>
                {showResearchPanel && (
                    <motion.div
                        key="research-status"
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 16 }}
                        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
                        className="fixed left-1/2 -translate-x-1/2 bottom-24 md:bottom-28 z-40 w-full px-4 pointer-events-none"
                    >
                        <div className="max-w-[900px] mx-auto flex justify-center">
                            <Card className="bg-gray-900/90 border border-gray-700 shadow-xl pointer-events-auto">
                                <CardContent className="px-4 py-3">
                                    {panelState === 'in-progress' && (
                                        <div className="flex items-center gap-2 text-blue-300">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                            <span className="text-sm font-medium">{researchProgress || 'Researching…'}</span>
                                        </div>
                                    )}
                                    {panelState === 'completed' && (
                                        <div className="flex items-center gap-2 text-green-300">
                                            <CheckCircle className="w-4 h-4" />
                                            <span className="text-sm font-medium">Research completed</span>
                                        </div>
                                    )}
                                    {panelState === 'stopped' && (
                                        <div className="flex items-center gap-2 text-orange-300">
                                            <AlertCircle className="w-4 h-4" />
                                            <span className="text-sm font-medium">Research stopped</span>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Messages */}
            <div
                ref={messagesContainerRef}
                className="flex-1 min-h-0 overflow-y-auto pt-6 custom-scrollbar relative"
            >
                {/* Centered container for all messages */}
                <div className="w-full max-w-[900px] mx-auto px-4 space-y-6">
                    {stableView?.map((m, index) => (
                        <div
                            key={m.id}
                            ref={(el) => {
                                if (el) messageRefs.current.set(m.id, el)
                                else messageRefs.current.delete(m.id)
                            }}
                            className={`flex ${m.role === 'assistant' ? 'justify-start' : 'justify-end'} ${index > 0 ? 'mt-6' : ''}`}
                        >
                            {m.role === 'user' ? (
                                <div className="max-w-[85%]">
                                    <div className="rounded-2xl px-4 py-2 bg-gray-800/70 border border-gray-700 text-gray-100 break-all">
                                        {m.content}
                                        {Array.isArray(m.files) && m.files.length > 0 && (
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {m.files.map((f, idx) => (
                                                    <div key={idx} className="flex items-center gap-2 bg-gray-700/60 border border-gray-600 rounded-lg px-2 py-1 text-xs text-gray-200">
                                                        <File className="w-3.5 h-3.5 text-blue-400" />
                                                        <span className="truncate max-w-40">{f.file?.name || 'attachment'}</span>
                                                        {f.importance && (
                                                            <span className={`px-1.5 py-0.5 rounded ${f.importance === 'high'
                                                                ? 'bg-red-500/30 text-red-300'
                                                                : f.importance === 'medium'
                                                                    ? 'bg-yellow-500/30 text-yellow-300'
                                                                    : 'bg-blue-500/30 text-blue-300'
                                                                }`}>
                                                                {f.importance}
                                                            </span>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                    {m.createdAt && (
                                        <div className="mt-1 text-[10px] text-gray-500 text-right">
                                            {new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="w-full text-gray-100 leading-relaxed break-words">
                                    {/* Embedded images at top for the latest assistant message */}
                                    {m.id === lastAssistantId && Array.isArray(researchImages) && researchImages.length > 0 && (
                                        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }} className="mb-3">
                                            <div className="-mx-1 overflow-x-auto no-scrollbar">
                                                <div className="px-1 flex gap-3 snap-x snap-mandatory">
                                                    {researchImages.map((img, idx) => (
                                                        <div key={idx} className="flex-shrink-0 snap-start">
                                                            <img
                                                                src={img.file_url || img.url}
                                                                alt={img.title || 'Research image'}
                                                                className="w-[260px] h-40 object-cover rounded-xl border border-gray-700"
                                                                loading="lazy"
                                                            />
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </motion.div>
                                    )}
                                    {m.streaming ? (
                                        <StreamingMessageView text={m.content || ''} />
                                    ) : (
                                        <div className="md max-w-none">
                                            <ThinkingMarkdown>
                                                {m.content || ''}
                                            </ThinkingMarkdown>
                                        </div>
                                    )}

                                    {/* YouTube embedded videos for this research (only on the latest assistant message) */}
                                    {m.id === lastAssistantId && (
                                        (() => {
                                            const ytVideos = researchMetadata?.youtube?.videos
                                                ? researchMetadata.youtube.videos
                                                : []
                                            const refGroups = getReferenceGroups(researchMetadata?.references)
                                            const refYt = refGroups.youtube || []
                                            // Prefer structured youtube.videos; fallback to youtube refs
                                            const videosToShow = Array.isArray(ytVideos) && ytVideos.length > 0
                                                ? ytVideos
                                                : refYt.map(v => ({ url: v.url, title: v.title, channel: v.channel, thumbnail: v.thumbnail }))

                                            if (!videosToShow || videosToShow.length === 0) return null

                                            return (
                                                <div className="mt-4">
                                                    <div className="text-sm font-semibold text-gray-200 mb-2">Video Resources</div>
                                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                        {videosToShow.slice(0, 2).map((video, idx) => {
                                                            const embed = buildEmbedUrl(video.url)
                                                            if (!embed) return null
                                                            return (
                                                                <div key={idx} className="bg-gray-900/70 border border-gray-700 rounded-xl overflow-hidden">
                                                                    <div className="aspect-video w-full bg-black">
                                                                        <iframe
                                                                            src={embed}
                                                                            title={video.title || `YouTube video ${idx + 1}`}
                                                                            className="w-full h-full"
                                                                            frameBorder="0"
                                                                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                                                            allowFullScreen
                                                                        />
                                                                    </div>
                                                                    {(video.title || video.channel) && (
                                                                        <div className="px-3 py-2 border-t border-gray-700">
                                                                            {video.title && <div className="text-sm text-gray-100 line-clamp-2">{video.title}</div>}
                                                                            {video.channel && <div className="text-xs text-gray-400">by {video.channel}</div>}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                </div>
                                            )
                                        })()
                                    )}

                                    {/* Sources / References list (web + news + fallback 'sources') */}
                                    {m.id === lastAssistantId && (
                                        (() => {
                                            const hasStructuredRefs = Array.isArray(researchMetadata?.references) && researchMetadata.references.length > 0
                                            const refGroups = hasStructuredRefs ? getReferenceGroups(researchMetadata.references) : { web: [], news: [], youtube: [] }
                                            const hasWeb = (refGroups.web?.length || 0) > 0
                                            const hasNews = (refGroups.news?.length || 0) > 0
                                            const hasFallbackSources = Array.isArray(researchSources) && researchSources.length > 0

                                            if (!hasWeb && !hasNews && !hasFallbackSources) return null

                                            return (
                                                <div className="mt-4">
                                                    <div className="text-sm font-semibold text-gray-200 mb-2">Sources</div>
                                                    <div className="space-y-3">
                                                        {hasWeb && (
                                                            <div className="bg-gray-900/70 border border-gray-700 rounded-xl p-3">
                                                                <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">Web</div>
                                                                <ul className="space-y-2 list-decimal pl-5">
                                                                    {refGroups.web.map((ref) => (
                                                                        <li key={`web-${ref.id || ref.url}`} className="text-sm">
                                                                            <a href={ref.url} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 break-words">
                                                                                {ref.title || ref.url}
                                                                            </a>
                                                                            {ref.snippet && (
                                                                                <div className="text-xs text-gray-400 mt-1">{ref.snippet}</div>
                                                                            )}
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            </div>
                                                        )}
                                                        {hasNews && (
                                                            <div className="bg-gray-900/70 border border-gray-700 rounded-xl p-3">
                                                                <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">News</div>
                                                                <ul className="space-y-2 list-decimal pl-5">
                                                                    {refGroups.news.map((ref) => (
                                                                        <li key={`news-${ref.id || ref.url}`} className="text-sm">
                                                                            <a href={ref.url} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 break-words">
                                                                                {ref.title || ref.url}
                                                                            </a>
                                                                            <div className="text-xs text-gray-400 mt-1">
                                                                                {(ref.source ? `${ref.source}` : '')}{ref.source && ref.date ? ' • ' : ''}{ref.date || ''}
                                                                            </div>
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            </div>
                                                        )}
                                                        {!hasStructuredRefs && hasFallbackSources && (
                                                            <div className="bg-gray-900/70 border border-gray-700 rounded-xl p-3">
                                                                <ul className="space-y-2 list-decimal pl-5">
                                                                    {researchSources.map((url, idx) => (
                                                                        <li key={`src-${idx}`} className="text-sm">
                                                                            <a href={url} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 break-words">
                                                                                {url}
                                                                            </a>
                                                                        </li>
                                                                    ))}
                                                                </ul>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )
                                        })()
                                    )}
                                    {/* Assistant actions */}
                                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                                        <button
                                            onClick={() => navigator.clipboard?.writeText(m.content || '')}
                                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-gray-700 bg-gray-800/60 hover:bg-gray-700 text-gray-200"
                                            title="Copy"
                                        >
                                            <Copy className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                            onClick={() => {
                                                try {
                                                    const u = new SpeechSynthesisUtterance(m.content || '')
                                                    window.speechSynthesis?.speak(u)
                                                } catch { }
                                            }}
                                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-gray-700 bg-gray-800/60 hover:bg-gray-700 text-gray-200"
                                            title="Read aloud"
                                        >
                                            <Volume2 className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                            onClick={() => console.log('regenerate requested for message', m.id)}
                                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-gray-700 bg-gray-800/60 hover:bg-gray-700 text-gray-200"
                                            title="Regenerate"
                                        >
                                            <RefreshCw className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                            onClick={() => console.log('retouch requested for message', m.id)}
                                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-gray-700 bg-gray-800/60 hover:bg-gray-700 text-gray-200"
                                            title="Retouch"
                                        >
                                            <Sparkles className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Streaming Assistant Message */}
                    {streamingIdx >= 0 && messages[streamingIdx]?.role === 'assistant' && messages[streamingIdx]?.streaming === true && (
                        <div
                            key={messages[streamingIdx].id}
                            className="flex justify-start mt-6"
                            ref={(el) => {
                                if (!el) return
                                const elContainer = messagesContainerRef.current
                                if (!elContainer) return
                                if (lastUserAlignedRef.current) {
                                    // Do not auto-pin while we keep gap, user can still scroll manually
                                    setIsPinnedToBottom(false)
                                }
                            }}
                        >
                            <div className="w-full text-gray-100 leading-relaxed break-words">
                                <StreamingMessageView text={messages[streamingIdx].content || ''} />
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Composer */}
            <div className="p-3">
                <motion.div
                    initial={{ y: 20, opacity: 0, borderRadius: 999 }}
                    animate={{ y: 0, opacity: 1, borderRadius: isMultiline ? 14 : 999 }}
                    transition={{ type: 'spring', stiffness: 220, damping: 22, mass: 0.6 }}
                    className={`bg-gray-800/80 border border-gray-700 p-3 overflow-hidden w-full max-w-[900px] mx-auto`}
                >
                    <div className={`flex ${isMultiline ? 'items-end' : 'items-center'} gap-3`}>
                        <DropdownMenu onOpenChange={setIsFileDropdownOpen}>
                            <DropdownMenuTrigger asChild>
                                <button className={`inline-flex items-center justify-center p-3 text-gray-400 hover:text-gray-200 hover:bg-gray-600 ${isMultiline ? 'rounded-md' : 'rounded-full'} transition-all duration-200 border ${isFileDropdownOpen ? 'border-gray-700/40 bg-gray-700/20' : 'border-transparent'}`}>
                                    <Paperclip className="w-5 h-5" />
                                </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent className="bg-gray-800 border border-gray-600 rounded-lg shadow-lg z-50" sideOffset={8}>
                                {fileTypes.map((type) => (
                                    <DropdownMenuItem
                                        key={type.id}
                                        onClick={() => setTimeout(() => triggerFileInput(type.name), 50)}
                                        className="group text-gray-200 hover:text-white focus:text-white hover:bg-gray-700 focus:bg-gray-700 cursor-pointer px-3 py-2"
                                    >
                                        <type.icon className="w-4 h-4 mr-2" />
                                        <div>
                                            <div className="font-medium">{type.name}</div>
                                            <div className="text-xs text-gray-400">{type.description}</div>
                                        </div>
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>

                        <div className="flex-1 relative">
                            <textarea
                                ref={textareaRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask me to research anything..."
                                className="w-full bg-transparent text-gray-100 placeholder-gray-400 resize-none outline-none min-h-[24px] max-h-[200px] leading-relaxed"
                                style={{ height: '24px' }}
                            />

                            {/* Attachments Preview */}
                            {attachedFiles.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {attachedFiles.map((attachment, index) => (
                                        <div key={index} className="flex items-center gap-2 bg-gray-700/50 rounded-lg px-3 py-2">
                                            {attachment.preview ? (
                                                <img
                                                    src={attachment.preview}
                                                    alt="attachment"
                                                    className="w-6 h-6 object-cover rounded"
                                                />
                                            ) : (
                                                <FileText className="w-4 h-4 text-gray-400" />
                                            )}
                                            <span className="text-sm text-gray-300 truncate max-w-[100px]">
                                                {attachment.file.name}
                                            </span>
                                            <select
                                                value={attachment.importance}
                                                onChange={(e) => updateAttachmentImportance(index, e.target.value)}
                                                className="text-xs bg-gray-600 border border-gray-500 rounded px-1 py-0.5"
                                            >
                                                <option value="low">Low</option>
                                                <option value="medium">Medium</option>
                                                <option value="high">High</option>
                                            </select>
                                            <button
                                                onClick={() => removeAttachment(index)}
                                                className="text-red-400 hover:text-red-300"
                                            >
                                                ×
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={handleSend}
                            disabled={isProcessing || (!input.trim() && attachedFiles.length === 0)}
                            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white p-3 rounded-lg transition-colors duration-200 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus:ring-0"
                        >
                            {isProcessing ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </motion.button>
                    </div>
                </motion.div>

                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                />
            </div>
        </div>
    )
}

export default ResearchArea
