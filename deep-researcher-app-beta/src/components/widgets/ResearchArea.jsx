import React, { useState, useRef, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Paperclip, Send, Loader2, Copy, Volume2, RefreshCw, Sparkles, ChevronDown, ExternalLink, Clock, FileText as FileTextIcon, Image as ImageIcon, Newspaper, BarChart3, Link, Search, Zap, Brain, Globe, Database, CheckCircle, AlertCircle, Play, Pause, Square } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../ui/dropdown-menu'
import { FileText, Image, File } from 'lucide-react'
import { Badge } from '../ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import StreamingMessageView from './StreamingMessageView'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import '../../md.css'

const ResearchArea = ({
    messages,
    onSend,
    isProcessing,
    researchProgress = '',
    researchSources = [],
    researchImages = [],
    researchNews = null,
    researchMetadata = null
}) => {
    const [input, setInput] = useState('')
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

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current
        if (!textarea) return

        const adjustHeight = () => {
            textarea.style.height = 'auto'
            const scrollHeight = textarea.scrollHeight
            const maxHeight = 200 // Maximum height in pixels
            textarea.style.height = Math.min(scrollHeight, maxHeight) + 'px'

            // Enable multiline mode if content is tall enough
            setIsMultiline(scrollHeight > 60)
        }

        textarea.addEventListener('input', adjustHeight)
        adjustHeight() // Initial adjustment

        return () => textarea.removeEventListener('input', adjustHeight)
    }, [input])

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

    // Render message content with proper formatting
    const renderMessageContent = (content, isUser = false) => {
        if (!content) return null

        return (
            <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
                {isUser ? (
                    <div className="whitespace-pre-wrap break-words">{content}</div>
                ) : (
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        className="prose prose-invert prose-sm max-w-none"
                        components={{
                            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                            h1: ({ children }) => <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0">{children}</h1>,
                            h2: ({ children }) => <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h2>,
                            h3: ({ children }) => <h3 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h3>,
                            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                            li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                            code: ({ inline, children }) => inline ?
                                <code className="bg-gray-700 px-1 py-0.5 rounded text-xs font-mono">{children}</code> :
                                <code className="block bg-gray-700 p-3 rounded-md text-sm font-mono overflow-x-auto">{children}</code>,
                            blockquote: ({ children }) => <blockquote className="border-l-4 border-gray-500 pl-4 italic my-2">{children}</blockquote>,
                            a: ({ href, children }) => <a href={href} className="text-blue-400 hover:text-blue-300 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                            strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                            em: ({ children }) => <em className="italic">{children}</em>,
                        }}
                    >
                        {content}
                    </ReactMarkdown>
                )}
            </div>
        )
    }

    // Get importance color
    const getImportanceColor = (importance) => {
        switch (importance) {
            case 'high': return 'text-red-400 bg-red-400/20'
            case 'medium': return 'text-yellow-400 bg-yellow-400/20'
            case 'low': return 'text-green-400 bg-green-400/20'
            default: return 'text-gray-400 bg-gray-400/20'
        }
    }

    return (
        <div className="flex-1 min-h-0 flex flex-col relative">
            {/* Floating Research Summary - Right Side */}
            {(isProcessing || researchProgress || researchMetadata) && (
                <div className="fixed right-4 top-1/2 transform -translate-y-1/2 z-50">
                    <Card className="bg-gray-800/95 border-gray-700 shadow-2xl backdrop-blur-sm">
                        <CardContent className="p-4 min-w-[200px]">
                            <div className="text-center space-y-3">
                                {/* Header - Show progress or completion */}
                                {researchMetadata ? (
                                    <div className="flex items-center justify-center gap-2 text-green-400">
                                        <CheckCircle className="w-4 h-4" />
                                        <span className="text-sm font-medium">Research completed!</span>
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center gap-2 text-blue-400">
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span className="text-sm font-medium">Research in progress...</span>
                                    </div>
                                )}

                                {/* Title */}
                                <h4 className="text-gray-200 text-sm font-medium">Research Summary</h4>

                                {/* Progress or Stats */}
                                {researchMetadata ? (
                                    <div className="grid grid-cols-2 gap-2 text-center">
                                        <div className="bg-gray-700/50 rounded p-2">
                                            <div className="text-lg font-bold text-blue-400">{researchMetadata.sources_count || 0}</div>
                                            <div className="text-xs text-gray-400">Sources</div>
                                        </div>
                                        <div className="bg-gray-700/50 rounded p-2">
                                            <div className="text-lg font-bold text-green-400">{researchMetadata.images_count || 0}</div>
                                            <div className="text-xs text-gray-400">Images</div>
                                        </div>
                                        <div className="bg-gray-700/50 rounded p-2">
                                            <div className="text-lg font-bold text-purple-400">{researchMetadata.news_count || 0}</div>
                                            <div className="text-xs text-gray-400">News</div>
                                        </div>
                                        <div className="bg-gray-700/50 rounded p-2">
                                            <div className="text-lg font-bold text-orange-400">{researchMetadata.research_time ? researchMetadata.research_time.toFixed(1) : '0.0'}</div>
                                            <div className="text-xs text-gray-400">Seconds</div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="text-center">
                                        <div className="text-gray-300 text-sm mb-2">
                                            {researchProgress || 'Initializing...'}
                                        </div>
                                        <div className="w-full bg-gray-700 rounded-full h-2">
                                            <div className="bg-blue-500 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Messages */}
            <div
                ref={messagesContainerRef}
                className="flex-1 min-h-0 overflow-y-auto pt-6 custom-scrollbar relative"
            >
                {/* Centered container for all messages */}
                <div className="w-full max-w-[900px] mx-auto px-4 space-y-6">
                    {stableView.map((message, index) => (
                        <motion.div
                            key={message.id || `msg-${index}`}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.3, delay: index * 0.05 }}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div className={`max-w-full ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                                {/* Message Header */}
                                <div className={`flex items-center gap-2 mb-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${message.role === 'user'
                                        ? 'bg-blue-500/20 text-blue-300'
                                        : ' text-purple-300'
                                        }`}>
                                        {message.role === 'user' ? (
                                            <>
                                                <Brain className="w-3 h-3" />
                                                You
                                            </>
                                        ) : (
                                            <>
                                                <Search className="w-3 h-3" />
                                                Deep Researcher
                                            </>
                                        )}
                                    </div>
                                    {message.createdAt && (
                                        <span className="text-xs text-gray-500">
                                            {new Date(message.createdAt).toLocaleTimeString()}
                                        </span>
                                    )}
                                </div>

                                {/* Message Content */}
                                <div className={`rounded-2xl px-4 py-3 shadow-lg ${message.role === 'user'
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-800 border border-gray-700 text-gray-100'
                                    }`}>
                                    {renderMessageContent(message.content, message.role === 'user')}

                                    {/* Attachments */}
                                    {message.files && message.files.length > 0 && (
                                        <div className="mt-3 space-y-2">
                                            {message.files.map((file, fileIndex) => (
                                                <div key={fileIndex} className={`flex items-center gap-2 p-2 rounded-lg ${message.role === 'user' ? 'bg-blue-500/20' : 'bg-gray-700/50'
                                                    }`}>
                                                    <FileText className="w-4 h-4" />
                                                    <span className="text-sm truncate">
                                                        {file.file?.name || 'attachment'}
                                                    </span>
                                                    <Badge className={`text-xs ${getImportanceColor(file.importance)}`}>
                                                        {file.importance}
                                                    </Badge>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </motion.div>
                    ))}

                    {/* Streaming Assistant Message */}
                    {streamingIdx >= 0 && messages[streamingIdx]?.role === 'assistant' && messages[streamingIdx]?.streaming === true && (
                        <div
                            key={messages[streamingIdx].id}
                            className="flex justify-start"
                            ref={(el) => {
                                const elContainer = messagesContainerRef.current
                                if (!elContainer) return
                                if (lastUserAlignedRef.current) {
                                    // Calculate if this streaming message should align user message to top
                                    const containerRect = elContainer.getBoundingClientRect()
                                    const messageRect = el.getBoundingClientRect()
                                    const isVisible = messageRect.top >= containerRect.top && messageRect.bottom <= containerRect.bottom

                                    if (!isVisible && messages.length > 1) {
                                        const lastUser = [...messages].reverse().find(m => m && m.role === 'user')
                                        if (lastUser && lastUser.id !== lastAlignedStreamIdRef.current) {
                                            lastAlignedStreamIdRef.current = lastUser.id
                                            // Align user message to top
                                            const userIndex = messages.findIndex(m => m.id === lastUser.id)
                                            if (userIndex >= 0) {
                                                const userElement = messageRefs.current.get(lastUser.id)
                                                if (userElement) {
                                                    userElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
                                                    lastUserAlignedRef.current = userElement
                                                    pendingAlignUserToTopRef.current = true
                                                    setTimeout(() => {
                                                        pendingAlignUserToTopRef.current = false
                                                    }, 500)
                                                }
                                            }
                                        }
                                    }
                                }
                            }}
                        >
                            <div className="max-w-full">
                                {/* Streaming Message Header */}
                                <div className={`flex items-center gap-2 mb-2 ${'justify-start'}`}>
                                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-purple-500/20 text-purple-300`}>
                                        <Search className="w-3 h-3" />
                                        Deep Researcher
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                    </div>
                                    {messages[streamingIdx].createdAt && (
                                        <span className="text-xs text-gray-500">
                                            {new Date(messages[streamingIdx].createdAt).toLocaleTimeString()}
                                        </span>
                                    )}
                                </div>

                                {/* Streaming Content - Same as ChatArea */}
                                <div className={`rounded-2xl px-4 py-3 shadow-lg text-gray-100`}>
                                    <div className="w-full text-gray-100 leading-relaxed break-words">
                                        <StreamingMessageView text={messages[streamingIdx].content || ''} />
                                    </div>
                                </div>
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
