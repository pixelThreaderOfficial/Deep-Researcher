import React, { useState, useEffect, useRef, useMemo } from 'react'
import { motion } from 'framer-motion'
// import ReactMarkdown from 'react-markdown'
// import remarkGfm from 'remark-gfm'
// import StreamingMonaco from './StreamingMonaco'
// import CodeBlock from './CodeBlock'
import ThinkingMarkdown from './ThinkingMarkdown'

export default function StreamingMessageView({ text }) {
    const [isStreaming, setIsStreaming] = useState(true)
    const [tokens, setTokens] = useState([])
    const [lastText, setLastText] = useState('')
    const containerRef = useRef(null)
    const prevTextRef = useRef('')

    // Detect streaming state
    useEffect(() => {
        const timer = setTimeout(() => {
            if (text === prevTextRef.current) {
                setIsStreaming(false)
            }
        }, 1000)

        if (text !== prevTextRef.current) {
            setIsStreaming(true)
        }

        prevTextRef.current = text
        return () => clearTimeout(timer)
    }, [text])

    // Track new tokens for fade-in effect
    useEffect(() => {
        if (text !== lastText) {
            if (text.length < lastText.length) {
                // Reset on new message
                setTokens([])
                setLastText('')
                return
            }

            // Get new content
            const newContent = text.slice(lastText.length)
            if (newContent) {
                // Split new content into tokens (words, punctuation, whitespace)
                const newTokens = newContent.match(/\S+|\s+/g) || []

                const tokenObjects = newTokens.map((token, idx) => ({
                    id: `${Date.now()}-${tokens.length + idx}`,
                    content: token,
                    isNew: true
                }))

                setTokens(prev => [...prev, ...tokenObjects])
                setLastText(text)

                // Remove "new" flag after animation
                setTimeout(() => {
                    setTokens(prev => prev.map(token => ({ ...token, isNew: false })))
                }, 500)
            }
        }
    }, [text, lastText, tokens.length])

    return (
        <motion.div
            className="md max-w-none relative"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
        >
            {/* Real-time markdown with token-based fade effect */}
            <motion.div
                key={tokens.length} // Re-animate when new tokens arrive
                initial={{ opacity: 0.8 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="streaming-content"
            >
                <ThinkingMarkdown>
                    {text || ''}
                </ThinkingMarkdown>
            </motion.div>

            {/* Blinking cursor */}
            {isStreaming && (
                <motion.span
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: "easeInOut" }}
                    className="inline-block w-0.5 h-4 bg-orange-400 align-middle ml-1"
                />
            )}

            <span ref={containerRef} />
        </motion.div>
    )
}


