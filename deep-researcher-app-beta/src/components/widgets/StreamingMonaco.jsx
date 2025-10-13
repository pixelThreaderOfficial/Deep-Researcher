import React, { useEffect, useRef, memo, useState } from 'react'
import Editor from '@monaco-editor/react'
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react'

function StreamingMonacoImpl({ language = 'plaintext', value = '', showHeader = true }) {
    const editorRef = useRef(null)
    const initialRef = useRef(true)
    const lastLangRef = useRef(language)
    const [copied, setCopied] = useState(false)
    const [isCollapsed, setIsCollapsed] = useState(false)

    // Calculate dynamic height based on content
    const calculateHeight = () => {
        if (isCollapsed) return 200 // Collapsed height

        const lines = (value || '').split('\n').length
        const lineHeight = 19 // Monaco's default line height
        const padding = 20 // Some padding
        const minHeight = 100
        const maxHeight = 800 // Maximum height to prevent extremely tall editors

        return Math.min(Math.max(lines * lineHeight + padding, minHeight), maxHeight)
    }

    const dynamicHeight = calculateHeight()

    useEffect(() => {
        if (!editorRef.current) return
        const model = editorRef.current.getModel?.()
        if (!model) return
        const prev = model.getValue()
        if (prev !== value) {
            model.setValue(value)
        }
    }, [value])

    const handleCopy = async () => {
        try {
            const current = editorRef.current?.getModel?.()?.getValue?.() ?? value
            await navigator.clipboard?.writeText(current)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        } catch { }
    }

    const handleToggleCollapse = () => {
        setIsCollapsed(!isCollapsed)
    }

    // Avoid tearing on final lines: freeze language to initial to prevent worker swap mid-stream
    const fixedLanguage = lastLangRef.current

    // Special handling for markdown: render as plain text with syntax highlighting
    const isMarkdown = fixedLanguage === 'markdown' || fixedLanguage === 'md'

    return (
        <div className="rounded-lg overflow-hidden border border-gray-700 bg-gray-900">
            {showHeader && (
                <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800 bg-gray-900/70">
                    <span className="text-xs text-gray-300">{fixedLanguage}</span>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleToggleCollapse}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-gray-700 bg-gray-800/60 hover:bg-gray-700 text-gray-200"
                            title={isCollapsed ? "Expand" : "Collapse"}
                        >
                            {isCollapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
                            {isCollapsed ? 'Expand' : 'Collapse'}
                        </button>
                        <button
                            onClick={handleCopy}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-gray-700 bg-gray-800/60 hover:bg-gray-700 text-gray-200"
                            title="Copy"
                        >
                            {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />} {copied ? 'Copied' : 'Copy'}
                        </button>
                    </div>
                </div>
            )}
            <div className="py-3" style={{ backgroundColor: '#1e1e1e' }}>
                {isMarkdown ? (
                    // For markdown, render as plain text with monospace font
                    <div
                        className="px-4 py-2 text-gray-200 font-mono text-sm leading-relaxed whitespace-pre-wrap overflow-auto"
                        style={{
                            height: `${dynamicHeight}px`,
                            backgroundColor: '#1e1e1e',
                            maxHeight: isCollapsed ? '200px' : '800px'
                        }}
                    >
                        {value}
                    </div>
                ) : (
                    <Editor
                        height={`${dynamicHeight}px`}
                        defaultLanguage={fixedLanguage}
                        defaultValue={value}
                        onMount={(editor) => {
                            editorRef.current = editor
                            // ensure initial value set exactly once
                            if (initialRef.current) {
                                const model = editor.getModel?.()
                                if (model && model.getValue() !== value) model.setValue(value)
                                initialRef.current = false
                            }
                        }}
                        options={{
                            readOnly: true,
                            minimap: { enabled: false },
                            scrollBeyondLastLine: false,
                            wordWrap: 'on',
                            automaticLayout: true
                        }}
                        theme="vs-dark"
                    />
                )}
            </div>
        </div>
    )
}

const StreamingMonaco = memo(StreamingMonacoImpl)
export default StreamingMonaco


