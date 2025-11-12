import React, { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip"
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuTrigger,
} from "@/components/ui/context-menu"
import { useNavigate, useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { Plus, Search, BookOpen, Folder, Cpu, /* Settings */ PanelRightClose, PanelRightOpen, Edit3, Trash2 } from 'lucide-react'



const ChatSidebar = ({
    recentChats = [],
    onNewChat,
    onSelectChat,
    onRenameChat,
    onDeleteChat,
    activeChatId,
}) => {
    const [query, setQuery] = useState('')
    const [collapsed, setCollapsed] = useState(false)
    const [headerHover, setHeaderHover] = useState(false)
    const [dbChats, setDbChats] = useState([])
    const [isLoadingChats, setIsLoadingChats] = useState(false)
    const navigate = useNavigate()
    const location = useLocation()

    // const isSettingsActive = location.pathname.startsWith('/app/settings') // settings hidden for now
    const isFilesActive = location.pathname.startsWith('/app/files')
    // Load sessions from API
    const loadChatsFromDatabase = async () => {
        try {
            setIsLoadingChats(true)
            const response = await fetch('http://localhost:8000/api/sessions?limit=50&offset=0')
            const data = await response.json()

            if (data.success && data.sessions) {
                // Convert to component format
                const formattedChats = data.sessions.map(session => ({
                    id: session.session_id,
                    title: session.title || `Chat ${session.id}`,
                    updatedAt: new Date(session.updated_at * 1000).toLocaleDateString(),
                    messageCount: session.stats?.total_messages || 0,
                    model: session.stats?.unique_models === 1 ? 'Single Model' : 'Multiple Models',
                    createdAt: new Date(session.created_at * 1000).toLocaleDateString()
                }))

                setDbChats(formattedChats)
            } else {
                console.error('Failed to load sessions:', data.error)
                setDbChats([])
            }
        } catch (error) {
            console.error('Failed to load chats:', error)
            // Fallback to empty array
            setDbChats([])
        } finally {
            setIsLoadingChats(false)
        }
    }

    useEffect(() => {
        try {
            const saved = localStorage.getItem('dr.sidebar.collapsed')
            if (saved === '1') setCollapsed(true)
        } catch { }
    }, [])

    useEffect(() => {
        try { localStorage.setItem('dr.sidebar.collapsed', collapsed ? '1' : '0') } catch { }
    }, [collapsed])

    // Load chats on component mount and when new chat is created
    useEffect(() => {
        loadChatsFromDatabase()
    }, [])

    // Refresh chats when a new chat is created (listen for changes)
    useEffect(() => {
        const refreshInterval = setInterval(() => {
            loadChatsFromDatabase()
        }, 30000) // Refresh every 30 seconds

        return () => clearInterval(refreshInterval)
    }, [])

    // Use database sessions if available, otherwise fall back to props
    const allChats = dbChats.length > 0 ? dbChats : recentChats

    const filtered = useMemo(() => {
        if (!query) return allChats
        const q = query.toLowerCase()
        return allChats.filter(c =>
            (c.title || '').toLowerCase().includes(q) ||
            (c.model || '').toLowerCase().includes(q)
        )
    }, [allChats, query])

    const isExpanded = !collapsed
    const widthPx = isExpanded ? 288 : 64

    return (
        <motion.aside
            className={cn('hidden md:flex shrink-0 h-screen sticky top-0 flex-col bg-gray-950/70 border-r border-gray-900/80 backdrop-blur-sm')}
            animate={{ width: widthPx }}
            initial={false}
            transition={{ type: 'spring', stiffness: 260, damping: 26 }}
        >
            {/* Header */}
            <div
                className={cn(' px-3 flex items-center justify-between border-b border-gray-900/70 shrink-0 py-3', !isExpanded && 'px-2')}
                onMouseEnter={() => setHeaderHover(true)}
                onMouseLeave={() => setHeaderHover(false)}
            >
                <div className={cn('flex items-center gap-3 min-w-0', !isExpanded && 'justify-center w-full')}>
                    {collapsed ? (

                        headerHover ? (
                            <Tooltip>
                                <TooltipTrigger>
                                    <motion.button
                                        key="toggle-left"
                                        className="inline-flex cursor-pointer items-center justify-center w-10 h-10 rounded-md border border-gray-800 bg-gray-900/60 text-gray-300 hover:bg-gray-800"
                                        onClick={() => setCollapsed(v => !v)}
                                        title="Expand"
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.96 }}
                                        transition={{ duration: 0.12 }}
                                    >
                                        <PanelRightClose className="w-5 h-5" />
                                    </motion.button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>Expand</p>
                                </TooltipContent>
                            </Tooltip>
                        ) : (
                            <motion.picture
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.96 }}
                                transition={{ duration: 0.12 }}
                            >
                                <source srcSet="/brand/Square284x284Logo.png" type="image/png" />
                                <img src="/brand/Square284x284Logo.png" alt="Deep Researcher" className={cn('select-none', 'h-10 w-10')} draggable={false} />
                            </motion.picture>
                        )


                    ) : (
                        <div
                            onClick={() => navigate('/')}
                            className='flex items-center gap-2 cursor-pointer'>
                            <picture>
                                <source srcSet="/brand/Square284x284Logo.png" type="image/png" />
                                <img src="/brand/Square284x284Logo.png" alt="Deep Researcher" className={cn('select-none', 'h-10 w-auto')} draggable={false} />
                            </picture>
                            <AnimatePresence initial={false}>
                                {isExpanded && (
                                    <motion.div
                                        key="brand-title"
                                        className="truncate"
                                        initial={{ opacity: 0, x: -8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: -8 }}
                                        transition={{ duration: 0.15 }}
                                    >
                                        <div className="text-sm font-semibold text-gray-100 leading-tight">Deep Researcher</div>
                                        <div className="text-[10px] uppercase tracking-wider text-gray-500">Research OS</div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <AnimatePresence initial={false}>
                        {!collapsed && (
                            <Tooltip>
                                <TooltipTrigger>
                                    <motion.button
                                        key="togglebtn"
                                        className="inline-flex cursor-pointer items-center justify-center w-8 h-8 rounded-md border border-gray-800 bg-gray-900/60 text-gray-300 hover:bg-gray-800"
                                        onClick={() => setCollapsed(v => !v)}
                                        title={collapsed ? 'Expand' : 'Collapse'}
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.96 }}
                                        transition={{ duration: 0.12 }}
                                    >
                                        <PanelRightOpen className="w-4 h-4" />
                                    </motion.button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>Collapse</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Quick nav */}
            <motion.div
                className={cn('border-b border-gray-900/70 relative overflow-hidden', !isExpanded && 'px-2')}
                animate={{
                    paddingLeft: isExpanded ? 12 : 8,
                    paddingRight: isExpanded ? 12 : 8,
                    paddingTop: 8,
                    paddingBottom: 8
                }}
                transition={{ type: 'spring', stiffness: 260, damping: 26 }}
            >
                {/* Search bar - slides up when collapsed */}
                <motion.div
                    className="relative mb-2"
                    animate={{
                        y: isExpanded ? 0 : -60,
                        opacity: isExpanded ? 1 : 0,
                        height: isExpanded ? 'auto' : 0
                    }}
                    transition={{
                        type: 'spring',
                        stiffness: 300,
                        damping: 30,
                        opacity: { duration: 0.2 }
                    }}
                >
                    {/* <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search chats"
                        className="w-full pl-8 pr-3 py-2 rounded-md bg-slate-900 border border-gray-800 text-sm text-gray-200 placeholder:text-gray-500 outline-none focus:border-gray-700"
                    /> */}
                </motion.div>

                {/* Navigation items - transform between horizontal and vertical layout */}
                <motion.div
                    className={cn('grid gap-1')}
                    animate={{
                        gridTemplateColumns: isExpanded ? '1fr' : 'repeat(1, 1fr)',
                        justifyItems: isExpanded ? 'stretch' : 'center'
                    }}
                    transition={{ type: 'spring', stiffness: 260, damping: 26 }}
                >
                    {/* New Chat */}
                    <motion.div
                        animate={{
                            flexDirection: isExpanded ? 'row' : 'column',
                            alignItems: 'center',
                            gap: isExpanded ? 8 : 4,
                            marginBottom: isExpanded ? 0 : 16
                        }}
                        transition={{ type: 'spring', stiffness: 260, damping: 26 }}
                    >
                        {isExpanded ? (
                            <button
                                onClick={() => {
                                    // Navigate to research mode (home page)
                                    navigate('/')
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800/60 transition-colors"
                            >
                                <Plus className="w-4 h-4" />
                                <div className="flex flex-col text-start ps-3">
                                    <motion.span
                                        className="truncate"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        New Research
                                    </motion.span>
                                    <motion.span
                                        className="truncate text-xs text-gray-500"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Start a new research session.
                                    </motion.span>
                                </div>
                            </button>
                        ) : (
                            <Tooltip>
                                <TooltipTrigger>
                                    <button
                                        className="p-2 cursor-pointer text-gray-400 hover:text-gray-200"
                                        title="New Research"
                                        onClick={() => {
                                            // Navigate to research mode (home page)
                                            navigate('/')
                                        }}
                                    >
                                        <Plus className="w-4 h-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>New Research</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </motion.div>

                    {/* Library */}
                    <motion.div
                        animate={{
                            flexDirection: isExpanded ? 'row' : 'column',
                            alignItems: 'center',
                            gap: isExpanded ? 8 : 4,
                            marginBottom: isExpanded ? 0 : 16
                        }}
                        transition={{ type: 'spring', stiffness: 260, damping: 26 }}
                    >
                        {isExpanded ? (
                            <button
                                onClick={() => { navigate('/app/researches') }}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800/60 transition-colors"
                            >
                                <BookOpen className="w-4 h-4" />
                                <div className="flex flex-col text-start ps-3">
                                    <motion.span
                                        className="truncate"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        All Researches
                                    </motion.span>
                                    <motion.span
                                        className="truncate text-xs text-gray-500"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        List of your deep researches.
                                    </motion.span>
                                </div>
                            </button>
                        ) : (
                            <Tooltip>
                                <TooltipTrigger>
                                    <button onClick={() => { navigate('/app/researches') }} className="p-2 cursor-pointer text-gray-400 hover:text-gray-200" title="Library">
                                        <BookOpen className="w-4 h-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>All Researches</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </motion.div>

                    {/* Files */}
                    <motion.div
                        animate={{
                            flexDirection: isExpanded ? 'row' : 'column',
                            alignItems: 'center',
                            gap: isExpanded ? 8 : 4,
                            marginBottom: isExpanded ? 0 : 16
                        }}
                        transition={{ type: 'spring', stiffness: 260, damping: 26 }}
                    >
                        {isExpanded ? (
                            <button
                                onClick={() => navigate('/app/files')}
                                className={cn(
                                    "w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                                    isFilesActive
                                        ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                        : "text-gray-300 hover:bg-gray-800/60"
                                )}
                            >
                                <Folder className="w-4 h-4" />
                                <div className="flex flex-col text-start ps-3">
                                    <motion.span
                                        className="truncate"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Files
                                    </motion.span>
                                    <motion.span
                                        className="truncate text-xs text-gray-500"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        List of attached/generated files.
                                    </motion.span>
                                </div>
                            </button>
                        ) : (
                            <Tooltip>
                                <TooltipTrigger>
                                    <button
                                        onClick={() => navigate('/app/files')}
                                        className={cn(
                                            "p-2 cursor-pointer transition-colors",
                                            isFilesActive
                                                ? "text-green-400 bg-green-500/20 rounded-md"
                                                : "text-gray-400 hover:text-gray-200"
                                        )}
                                        title="Files"
                                    >
                                        <Folder className="w-4 h-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>Files</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </motion.div>

                    {/* Settings nav item hidden until implemented */}
                    {false && (
                        <motion.div
                            animate={{
                                flexDirection: isExpanded ? 'row' : 'column',
                                alignItems: 'center',
                                gap: isExpanded ? 8 : 4,
                                marginBottom: isExpanded ? 0 : 0
                            }}
                            transition={{ type: 'spring', stiffness: 260, damping: 26 }}
                        >
                            {/* Original settings button commented out */}
                        </motion.div>
                    )}
                </motion.div>
            </motion.div>

            {/* Recent Chats - Hidden as per user request */}
            {false && isExpanded && (
                <AnimatePresence initial={false}>
                    <motion.div
                        key="recent"
                        className="px-3 py-3"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.18 }}
                    >
                        <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">Recent</p>
                        <div className="space-y-1 max-h-[48vh] overflow-y-auto custom-scrollbar pr-1">
                            {filtered.length === 0 && (
                                <div className="text-sm text-gray-500 px-2 py-3">No chats found</div>
                            )}
                            <AnimatePresence initial={false}>
                                {filtered.map((chat) => (
                                    <ContextMenu key={chat.id}>
                                        <ContextMenuTrigger>
                                            <motion.button
                                                onClick={() => onSelectChat?.(chat.id)}
                                                className={cn(
                                                    'w-full text-left px-2 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-900/60 transition-colors',
                                                    activeChatId === chat.id && 'bg-gray-900/80 text-gray-100 border border-gray-800'
                                                )}
                                                initial={{ opacity: 0, y: 6 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: -6 }}
                                                transition={{ duration: 0.14 }}
                                            >
                                                <div className="truncate">{chat.title}</div>
                                                <div className="text-[11px] text-gray-500">{chat.updatedAt}</div>
                                            </motion.button>
                                        </ContextMenuTrigger>
                                        <ContextMenuContent className="bg-gray-800 border border-gray-600">
                                            <ContextMenuItem
                                                onClick={() => onSelectChat?.(chat.id)}
                                                className="text-gray-200 hover:bg-gray-700 focus:bg-gray-700"
                                            >
                                                <BookOpen className="w-4 h-4 mr-2" />
                                                Open Chat
                                            </ContextMenuItem>
                                            <ContextMenuItem
                                                onClick={() => {
                                                    const newTitle = prompt('Enter new title:', chat.title)
                                                    if (newTitle && newTitle.trim() && newTitle !== chat.title) {
                                                        onRenameChat?.(chat.id, newTitle.trim())
                                                    }
                                                }}
                                                className="text-gray-200 hover:bg-gray-700 focus:bg-gray-700"
                                            >
                                                <Edit3 className="w-4 h-4 mr-2" />
                                                Rename
                                            </ContextMenuItem>
                                            <ContextMenuItem
                                                onClick={() => {
                                                    if (confirm(`Are you sure you want to delete "${chat.title}"?`)) {
                                                        onDeleteChat?.(chat.id)
                                                    }
                                                }}
                                                className="text-red-400 hover:bg-red-900/20 focus:bg-red-900/20"
                                            >
                                                <Trash2 className="w-4 h-4 mr-2" />
                                                Delete
                                            </ContextMenuItem>
                                        </ContextMenuContent>
                                    </ContextMenu>
                                ))}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                </AnimatePresence>
            )}
        </motion.aside>
    )
}

export default ChatSidebar




