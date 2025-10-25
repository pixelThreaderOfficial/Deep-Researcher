import React, { useState, useMemo, useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { invoke } from '@tauri-apps/api/core'
import ChatSidebar from './ChatSidebar'
import ChatHeader from './ChatHeader'

const ChatLayout = () => {
    const navigate = useNavigate()
    const [recentChats, setRecentChats] = useState([])
    const [isLoadingChats, setIsLoadingChats] = useState(false)

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

            setRecentChats(formattedChats)
        } catch (error) {
            console.error('Failed to load chats from database:', error)
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
        const newId = `ch_${Date.now()}`
        try {
            // Create chat in database
            await invoke('cmd_create_chat', {
                id: newId,
                title: 'New Chat',
                model: 'granite3-moe' // Default model
            })

            // Add welcome message to database
            const welcomeMessage = { id: Date.now(), role: 'assistant', content: 'New chat started. What would you like to do?', createdAt: new Date().toISOString() }
            await invoke('cmd_add_message', {
                chatId: newId,
                role: welcomeMessage.role,
                content: welcomeMessage.content,
                files: null
            })

            // Navigate to the new chat
            navigate(`/chat/${newId}`)
        } catch (error) {
            console.error('Failed to create new chat:', error)
            // Fallback: navigate to chat page anyway
            navigate(`/chat/${newId}`)
        }
        // Refresh chats list after creating new chat
        setTimeout(() => loadChatsFromDatabase(), 100)
    }

    const handleSelectChat = (chatId) => {
        navigate(`/chat/${chatId}`)
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

    return (
        <div className="flex h-screen flex-col">

            {/* Main Application Content */}
            <div className="flex flex-1">
                {/* Sidebar */}
                <ChatSidebar
                    recentChats={recentChats}
                    onNewChat={handleNewChat}
                    onSelectChat={handleSelectChat}
                    activeChatId="ch_1"
                />

                {/* Main Content Area */}
                <div className="flex-1 flex flex-col">
                    {/* Chat Header */}
                    <ChatHeader
                        onOpenSettings={handleOpenSettings}
                        model="granite3-moe"
                        chatInfo={chatInfo}
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
