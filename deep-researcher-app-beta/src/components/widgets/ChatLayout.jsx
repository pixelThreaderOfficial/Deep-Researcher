import React, { useState, useMemo, useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import ChatSidebar from './ChatSidebar'
import ChatHeader from './ChatHeader'

const ChatLayout = () => {
    const navigate = useNavigate()
    const location = useLocation()
    const [recentChats, setRecentChats] = useState([])
    const [isLoadingChats, setIsLoadingChats] = useState(false)

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
                    model: session.stats?.unique_models === 1 ? 'Single Model' : 'Multiple Models'
                }))

                setRecentChats(formattedChats)
            } else {
                console.error('Failed to load sessions:', data.error)
                setRecentChats([])
            }
        } catch (error) {
            console.error('Failed to load chats:', error)
            // Fallback to empty array
            setRecentChats([])
        } finally {
            setIsLoadingChats(false)
        }
    }

    useEffect(() => {
        loadChatsFromDatabase()
    }, [])

    const handleNewChat = async () => {
        // Generate a new UUID for the session (frontend generates, backend will use it)
        const newSessionId = `550e8400-e29b-41d4-a716-${Date.now().toString(16).padStart(12, '0')}`

        try {
            // Navigate to the new chat first (it will create the session when first message is sent)
            navigate(`/chat/${newSessionId}`)
        } catch (error) {
            console.error('Failed to create new chat:', error)
            // Fallback: navigate to chat page anyway
            navigate(`/chat/${newSessionId}`)
        }

        // Refresh chats list after creating new chat
        setTimeout(() => loadChatsFromDatabase(), 100)
    }

    const handleSelectChat = (chatId) => {
        navigate(`/chat/${chatId}`)
    }

    const handleRenameChat = async (chatId, newTitle) => {
        try {
            const response = await fetch(`http://localhost:8000/api/sessions/${chatId}/title`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle }),
            })
            const data = await response.json()

            if (data.success) {
                // Refresh the chats list
                loadChatsFromDatabase()
            } else {
                console.error('Failed to rename chat:', data.error)
                alert('Failed to rename chat')
            }
        } catch (error) {
            console.error('Error renaming chat:', error)
            alert('Error renaming chat')
        }
    }

    const handleDeleteChat = async (chatId) => {
        try {
            const response = await fetch(`http://localhost:8000/api/sessions/${chatId}`, {
                method: 'DELETE',
            })
            const data = await response.json()

            if (data.success) {
                // Refresh the chats list
                loadChatsFromDatabase()
                // If the deleted chat was active, navigate away
                if (chatId === 'ch_1') { // You might want to track the active chat ID properly
                    navigate('/')
                }
            } else {
                console.error('Failed to delete chat:', data.error)
                alert('Failed to delete chat')
            }
        } catch (error) {
            console.error('Error deleting chat:', error)
            alert('Error deleting chat')
        }
    }

    const chatInfo = useMemo(() => ({
        messageCount: 0,
        createdAt: new Date().toISOString(),
        totalTokens: 0,
        totalFiles: 0,
        contextTokens: 0,
        nextPromptFiles: 0,
        lastResponseStats: null
    }), [])

    const handleOpenSettings = () => {
        navigate('/settings')
    }

    const pageTitle = (() => {
        const p = location.pathname || ''
        if (p.startsWith('/app/researches')) return 'Research History'
        if (p.startsWith('/app/research/')) return 'Research'
        if (p.startsWith('/app/files')) return 'Files'
        if (p.startsWith('/app/settings')) return 'Settings'
        if (p.startsWith('/app')) return 'Home'
        return 'Chat'
    })()

    return (
        <div className="flex h-screen flex-col">

            {/* Main Application Content */}
            <div className="flex flex-1">
                {/* Sidebar */}
                <ChatSidebar
                    recentChats={recentChats}
                    onNewChat={handleNewChat}
                    onSelectChat={handleSelectChat}
                    onRenameChat={handleRenameChat}
                    onDeleteChat={handleDeleteChat}
                    activeChatId="ch_1"
                />

                {/* Main Content Area */}
                <div className="flex-1 flex flex-col">
                    {/* Chat Header */}
                    <ChatHeader
                        onOpenSettings={handleOpenSettings}
                        model="granite3-moe"
                        chatInfo={chatInfo}
                        pageTitle={pageTitle}
                    />

                    {/* Content Area with Outlet */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                        <Outlet />
                    </div>
                </div>
            </div>
        </div>
    )
}

export default ChatLayout
