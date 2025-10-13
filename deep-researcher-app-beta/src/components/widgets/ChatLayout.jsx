import React, { useState, useMemo } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import ChatSidebar from './ChatSidebar'
import ChatHeader from './ChatHeader'

const ChatLayout = () => {
    const navigate = useNavigate()
    const [recentChats] = useState([
        { id: 'ch_1', title: 'Chat 1', updatedAt: 'just now' },
        { id: 'ch_2', title: 'Chat 2', updatedAt: '2 hours ago' },
        { id: 'ch_3', title: 'Chat 3', updatedAt: 'yesterday' },
    ])

    const handleNewChat = () => {
        console.log('New chat')
    }

    const handleSelectChat = (chatId) => {
        console.log('Select chat:', chatId)
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
