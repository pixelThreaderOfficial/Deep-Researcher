import React, { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Paperclip, Send, Loader2, Copy, Volume2, RefreshCw, Sparkles, ChevronDown } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../ui/dropdown-menu'
import { FileText, Image as ImageIcon, File } from 'lucide-react'
import '../../md.css'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'
import StreamingMessageView from './StreamingMessageView'
import ThinkingMarkdown from './ThinkingMarkdown'

const ChatArea = ({ messages, onSend, isProcessing }) => {
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
            const threshold = 32 // px tolerance to treat as bottom
            const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight)
            const atBottom = distanceFromBottom <= threshold
            setIsPinnedToBottom(atBottom)
        }

        el.addEventListener('scroll', handleScroll, { passive: true })
        // Initialize state once mounted
        handleScroll()

        // Observe content size changes to auto-scroll when pinned
        let resizeObserver
        if ('ResizeObserver' in window) {
            resizeObserver = new ResizeObserver(() => {
                if (isPinnedToBottom) {
                    el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
                }
            })
            resizeObserver.observe(el)
        }

        return () => {
            el.removeEventListener('scroll', handleScroll)
            if (resizeObserver) resizeObserver.disconnect()
        }
    }, [isPinnedToBottom])

    useEffect(() => {
        if (!textareaRef.current) return
        const el = textareaRef.current
        el.style.height = 'auto'
        el.style.height = `${Math.min(el.scrollHeight, 200)}px`
        const hasNewline = input.includes('\n')
        const overflowed = (el.scrollHeight - el.clientHeight) > 6
        const hasAttachments = attachedFiles.length > 0
        setIsMultiline(hasNewline || overflowed || hasAttachments)
    }, [input, attachedFiles.length])

    const getAcceptedFileTypes = (fileTypeName) => {
        switch (fileTypeName) {
            case 'Images':
                return 'image/*'
            case 'PDFs':
                return '.pdf'
            case 'Documents':
                return '.doc,.docx,.txt,.rtf,.odt'
            default:
                return 'image/*,.pdf,.doc,.docx,.txt,.rtf,.odt'
        }
    }

    const triggerFileInput = (fileTypeName = null) => {
        if (!fileInputRef.current) return
        if (fileTypeName) fileInputRef.current.accept = getAcceptedFileTypes(fileTypeName)
        fileInputRef.current.click()
    }

    const handleFileChange = (e) => {
        const files = Array.from(e.target.files || [])
        if (files.length === 0) return
        const withImportance = files.map((file) => ({ file, importance: 'medium' }))
        setAttachedFiles((prev) => [...prev, ...withImportance])
        e.target.value = ''
    }

    const updateFileImportance = (index, importance) => {
        setAttachedFiles((prev) => prev.map((f, i) => (i === index ? { ...f, importance } : f)))
    }

    const removeFile = (index) => {
        setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
    }

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            microphoneRef.current = stream
        } catch (err) {
            setIsRecording(false)
        }
    }

    const stopRecording = () => {
        try {
            if (microphoneRef.current) {
                microphoneRef.current.getTracks().forEach((t) => t.stop())
                microphoneRef.current = null
            }
        } catch (err) { }
    }

    const send = () => {
        const text = input.trim()
        if (!text && attachedFiles.length === 0) return
        onSend?.(text, attachedFiles)
        setInput('')
        setAttachedFiles([])
        // Defer alignment until after messages update so refs are present
        pendingAlignUserToTopRef.current = true
    }

    // After messages update (user message added), align that user message near the top
    useEffect(() => {
        if (!pendingAlignUserToTopRef.current) return
        const container = messagesContainerRef.current
        if (!container) return
        const lastUser = Array.isArray(messages)
            ? [...messages].reverse().find(m => m && m.role === 'user')
            : null
        if (!lastUser) {
            pendingAlignUserToTopRef.current = false
            return
        }
        const targetEl = messageRefs.current.get(lastUser.id)
        if (!targetEl) return
        // Next frame to ensure DOM layout is up-to-date
        requestAnimationFrame(() => {
            const contTop = container.getBoundingClientRect().top
            const elTop = targetEl.getBoundingClientRect().top
            const newTop = container.scrollTop + (elTop - contTop)
            // Also ensure the window is at page top
            try { window.scrollTo({ top: 0, behavior: 'smooth' }) } catch { }
            container.scrollTo({ top: Math.max(newTop, 0), behavior: 'smooth' })
            setIsPinnedToBottom(false)
            lastUserAlignedRef.current = lastUser.id
            pendingAlignUserToTopRef.current = false
        })
    }, [messages])

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

    const stableMessages = useMemo(() => {
        if (!Array.isArray(messages)) return []
        // Filter out the actively streaming message, but keep completed assistant messages
        if (streamingIdx >= 0) {
            return messages.filter((_, idx) => idx !== streamingIdx)
        }
        return messages
    }, [messages, streamingIdx])

    const stableKey = useMemo(() => {
        return JSON.stringify(stableMessages.map(m => [m.id, m.content]))
    }, [stableMessages])

    const stableView = useMemo(() => {
        const hasUserMessage = Array.isArray(stableMessages) && stableMessages.some(m => m.role === 'user')
        const isEmpty = Array.isArray(stableMessages) ? stableMessages.length === 0 : true
        return (
            <>
                <AnimatePresence>
                    {(!hasUserMessage && isEmpty) && (
                        <motion.div
                            key="greeting-spacer"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: '40vh', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 1, ease: 'easeInOut' }}
                            className="w-full"
                        >
                            <div className="h-full w-full flex items-center justify-center text-center">
                                <div>
                                    <h2 className="text-4xl sm:text-6xl font-bold merienda text-gray-100">Good Afternoon, Mr. Rana</h2>
                                    <p className="mt-10 text-gray-400 text-base">Start a conversation or attach files for analysis.</p>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {stableMessages?.map((m, index) => (
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
                                {m.streaming ? (
                                    <StreamingMessageView text={m.content || ''} />
                                ) : (
                                    <div className="md max-w-none">
                                        <ThinkingMarkdown>
                                            {m.content || ''}
                                        </ThinkingMarkdown>
                                    </div>
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

                <AnimatePresence>
                    {isProcessing && (
                        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="flex items-center gap-2 text-gray-400 mt-4">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Thinking…
                        </motion.div>
                    )}
                </AnimatePresence>
                {/* spacer */}
                <div />
            </>
        )
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [stableKey, isProcessing])

    return (
        <div className="flex-1 min-h-0 flex flex-col">

            {/* Messages */}
            <div
                ref={messagesContainerRef}
                className="flex-1 min-h-0 overflow-y-auto pt-6 custom-scrollbar relative"
            >
                {/* Centered container for all messages */}
                <div className="w-full max-w-[900px] mx-auto px-4 space-y-6">
                    {stableView}
                    {streamingIdx >= 0 && messages[streamingIdx]?.role === 'assistant' && messages[streamingIdx]?.streaming === true && (
                        <div
                            key={messages[streamingIdx].id}
                            className="flex justify-start mt-6"
                            ref={(el) => {
                                if (!el) return
                                // When assistant starts streaming right after a user send, keep the user message at top
                                // and allow stream to push upward.
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

                {/* Scroll-to-bottom button */}
                {!isPinnedToBottom && (
                    <button
                        onClick={() => {
                            const el = messagesContainerRef.current
                            if (el) {
                                el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
                                setIsPinnedToBottom(true)
                            }
                        }}
                        className="fixed right-4 bottom-24 md:bottom-28 z-40 inline-flex items-center justify-center w-10 h-10 rounded-full bg-gray-800/90 border border-gray-700 text-gray-100 shadow-lg hover:bg-gray-700 transition-colors"
                        title="Scroll to bottom"
                    >
                        <ChevronDown className="w-5 h-5" />
                    </button>
                )}
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
                                            <div className="font-medium group-hover:text-white group-focus:text-white">{type.name}</div>
                                            <div className="text-xs text-gray-400 group-hover:text-gray-200 group-focus:text-gray-200">{type.description}</div>
                                        </div>
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>

                        <textarea
                            ref={textareaRef}
                            className={`flex-1 min-w-0 bg-transparent text-gray-100 resize-none outline-none text-base max-h-[200px] placeholder:text-gray-400 break-all ${isMultiline ? 'py-2 leading-relaxed min-h-[48px]' : 'h-[44px] min-h-[44px] leading-[44px] py-0'} px-0`}
                            placeholder="Ask anything… (Enter to send, Shift+Enter for new line)"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    send()
                                }
                            }}
                            rows={1}
                        />

                        <button
                            onClick={async () => {
                                if (!isRecording) {
                                    setIsRecording(true);
                                    try {
                                        await startRecording();
                                    } catch (err) {
                                        setIsRecording(false);
                                    }
                                }
                                else {
                                    setIsRecording(false);
                                    stopRecording()
                                }
                            }}
                            className={`inline-flex items-center justify-center p-3 ${isMultiline ? 'rounded-md' : 'rounded-full'} transition-colors duration-200 ${isRecording ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-gray-600 hover:bg-gray-500 text-gray-300'}`}
                        >
                            {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                        </button>

                        <button
                            onClick={send}
                            disabled={isProcessing || (!input.trim() && attachedFiles.length === 0)}
                            className={`inline-flex items-center justify-center bg-orange-500 hover:bg-orange-600 disabled:bg-gray-600 text-white p-3 ${isMultiline ? 'rounded-md' : 'rounded-full'} transition-colors duration-200 disabled:cursor-not-allowed`}
                        >
                            {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5 rotate-45 -translate-x-0.5" />}
                        </button>
                    </div>

                    {/* Hidden file input */}
                    <input ref={fileInputRef} type="file" className="hidden" multiple accept="image/*,.pdf,.doc,.docx,.txt,.rtf,.odt" onChange={handleFileChange} />

                    {/* Files */}
                    <AnimatePresence>
                        {attachedFiles.length > 0 && (
                            <motion.div className="mt-3 flex flex-wrap gap-2" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                                {attachedFiles.map((f, idx) => (
                                    <div key={idx} className="flex items-center gap-2 bg-gray-700 border border-gray-600 rounded-md px-3 py-2 text-sm text-gray-200">
                                        <File className="w-4 h-4 text-blue-400" />
                                        <span className="truncate max-w-36">{f.file.name}</span>
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <button className={`text-xs px-2 py-0.5 rounded-md ${f.importance === 'high' ? 'bg-red-500/30 text-red-300' : f.importance === 'medium' ? 'bg-yellow-500/30 text-yellow-300' : 'bg-blue-500/30 text-blue-300'}`}>{f.importance}</button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent className="bg-gray-800 border border-gray-600 rounded-lg shadow-lg z-50">
                                                <DropdownMenuItem onClick={() => updateFileImportance(idx, 'high')} className="text-red-300 hover:bg-gray-700 cursor-pointer">High</DropdownMenuItem>
                                                <DropdownMenuItem onClick={() => updateFileImportance(idx, 'medium')} className="text-yellow-300 hover:bg-gray-700 cursor-pointer">Medium</DropdownMenuItem>
                                                <DropdownMenuItem onClick={() => updateFileImportance(idx, 'low')} className="text-blue-300 hover:bg-gray-700 cursor-pointer">Low</DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                        <button onClick={() => removeFile(idx)} className="text-gray-400 hover:text-red-400 p-1 rounded-md">✕</button>
                                    </div>
                                ))}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>
            </div>
        </div>
    )
}

export default ChatArea


