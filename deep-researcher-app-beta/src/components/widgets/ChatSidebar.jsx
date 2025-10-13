import React, { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip"
import { Avatar, AvatarFallback } from '../ui/avatar'
import { useNavigate, useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'
import { Plus, Search, BookOpen, Folder, Cpu, Settings, PanelRightClose, PanelRightOpen } from 'lucide-react'
import { invoke } from '@tauri-apps/api/core'



const ChatSidebar = ({
    recentChats = [],
    onNewChat,
    onSelectChat,
    activeChatId,
}) => {
    const [query, setQuery] = useState('')
    const [collapsed, setCollapsed] = useState(false)
    const [headerHover, setHeaderHover] = useState(false)
    const [dbChats, setDbChats] = useState([])
    const [isLoadingChats, setIsLoadingChats] = useState(false)
    const navigate = useNavigate()
    const location = useLocation()

    const isSettingsActive = location.pathname.startsWith('/app/settings')
    const isFilesActive = location.pathname.startsWith('/app/files')
    // Load chats from database
    const loadChatsFromDatabase = async () => {
        try {
            setIsLoadingChats(true)
            const chats = await invoke('cmd_get_recent_chats', { limit: 50 })

            // Convert database format to component format
            const formattedChats = chats.map(chat => ({
                id: chat.id,
                title: chat.title,
                updatedAt: new Date(chat.updated_at).toLocaleDateString(),
            }))

            setDbChats(formattedChats)
        } catch (error) {
            console.error('Failed to load chats from database:', error)
            // Fallback to prop-based chats if database fails
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

    // Load chats on component mount
    useEffect(() => {
        loadChatsFromDatabase()
    }, [])

    // Use database chats if available, otherwise fall back to props
    const allChats = dbChats.length > 0 ? dbChats : recentChats

    const filtered = useMemo(() => {
        if (!query) return allChats
        const q = query.toLowerCase()
        return allChats.filter(c => (c.title || '').toLowerCase().includes(q))
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
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search chats"
                        className="w-full pl-8 pr-3 py-2 rounded-md bg-slate-900 border border-gray-800 text-sm text-gray-200 placeholder:text-gray-500 outline-none focus:border-gray-700"
                    />
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
                                    onNewChat()
                                    // Refresh chats from database after creating new chat
                                    setTimeout(() => loadChatsFromDatabase(), 100)
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
                                        New chat
                                    </motion.span>
                                    <motion.span
                                        className="truncate text-xs text-gray-500"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Create a new chat.
                                    </motion.span>
                                </div>
                            </button>
                        ) : (
                            <Tooltip>
                                <TooltipTrigger>
                                    <button
                                        className="p-2 cursor-pointer text-gray-400 hover:text-gray-200"
                                        title="New chat"
                                        onClick={() => {
                                            onNewChat()
                                            // Refresh chats from database after creating new chat
                                            setTimeout(() => loadChatsFromDatabase(), 100)
                                        }}
                                    >
                                        <Plus className="w-4 h-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>New chat</p>
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
                                onClick={() => { }}
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
                                    <button className="p-2 cursor-pointer text-gray-400 hover:text-gray-200" title="Library">
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

                    {/* Models */}
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
                                onClick={() => { }}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-800/60 transition-colors"
                            >
                                <Cpu className="w-4 h-4" />
                                <div className="flex flex-col text-start ps-3">
                                    <motion.span
                                        className="truncate"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Models
                                    </motion.span>
                                    <motion.span
                                        className="truncate text-xs text-gray-500"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Manage your AI models.
                                    </motion.span>
                                </div>
                            </button>
                        ) : (
                            <Tooltip>
                                <TooltipTrigger>
                                    <button className="p-2 cursor-pointer text-gray-400 hover:text-gray-200" title="Models">
                                        <Cpu className="w-4 h-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>Models</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </motion.div>

                    {/* Settings */}
                    <motion.div
                        animate={{
                            flexDirection: isExpanded ? 'row' : 'column',
                            alignItems: 'center',
                            gap: isExpanded ? 8 : 4,
                            marginBottom: isExpanded ? 0 : 0
                        }}
                        transition={{ type: 'spring', stiffness: 260, damping: 26 }}
                    >
                        {isExpanded ? (
                            <button
                                onClick={() => navigate('/app/settings')}
                                className={cn(
                                    "w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                                    isSettingsActive
                                        ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                        : "text-gray-300 hover:bg-gray-800/60"
                                )}
                            >
                                <Settings className="w-4 h-4" />
                                <div className="flex flex-col text-start ps-3">
                                    <motion.span
                                        className="truncate"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Settings
                                    </motion.span>
                                    <motion.span
                                        className="truncate text-xs text-gray-500"
                                        animate={{ opacity: isExpanded ? 1 : 0 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        Track files from your conversations.
                                    </motion.span>
                                </div>
                            </button>
                        ) : (
                            <Tooltip>
                                <TooltipTrigger>
                                    <button
                                        onClick={() => navigate('/app/settings')}
                                        className={cn(
                                            "p-2 cursor-pointer transition-colors",
                                            isSettingsActive
                                                ? "text-blue-400 bg-blue-500/20 rounded-md"
                                                : "text-gray-400 hover:text-gray-200"
                                        )}
                                        title="Settings"
                                    >
                                        <Settings className="w-4 h-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" align="center" className="bg-slate-900 text-gray-200 border border-gray-800" hideArrow={true} sideOffset={10}>
                                    <p>Settings</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </motion.div>
                </motion.div>
            </motion.div>

            {/* Recent Chats */}
            <AnimatePresence initial={false}>

                {isExpanded && (
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
                                    <motion.button
                                        key={chat.id}
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
                                ))}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Bottom Profile */}
            <div className={cn('mt-auto p-3 border-t border-gray-900/70', !isExpanded && 'flex items-center justify-center')}>
                <div className={cn('flex items-center gap-3', !isExpanded && 'gap-0')}>
                    <Avatar>
                        <AvatarFallback className="bg-gray-800 text-gray-200">U</AvatarFallback>
                    </Avatar>
                    <AnimatePresence initial={false}>
                        {isExpanded && (
                            <motion.div
                                key="profiletxt"
                                className="leading-tight min-w-0"
                                initial={{ opacity: 0, x: -8 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -8 }}
                                transition={{ duration: 0.15 }}
                            >
                                <div className="text-sm text-gray-100 truncate">Boss</div>
                                <div className="text-xs text-gray-500 truncate">boss@example.com</div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </motion.aside>
    )
}

export default ChatSidebar


