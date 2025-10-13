import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'

const ThinkingMarkdown = ({ children }) => {
    // Parse the content for <think> tags
    const parseThinkingContent = (content) => {
        if (!content) return [{ type: 'markdown', content: '' }]

        const parts = []
        let currentPos = 0

        // Find all <think> and </think> tags
        const thinkStartRegex = /<think>/gi
        const thinkEndRegex = /<\/think>/gi

        let thinkStartMatch
        let thinkEndMatch

        while ((thinkStartMatch = thinkStartRegex.exec(content)) !== null) {
            // Add content before <think> tag as regular markdown
            if (thinkStartMatch.index > currentPos) {
                parts.push({
                    type: 'markdown',
                    content: content.slice(currentPos, thinkStartMatch.index)
                })
            }

            // Find the corresponding </think> tag
            thinkEndRegex.lastIndex = thinkStartMatch.index + 7 // Skip past <think>
            thinkEndMatch = thinkEndRegex.exec(content)

            if (thinkEndMatch) {
                // Add thinking content
                const thinkingContent = content.slice(
                    thinkStartMatch.index + 7, // After <think>
                    thinkEndMatch.index
                )
                parts.push({
                    type: 'thinking',
                    content: thinkingContent.trim()
                })
                currentPos = thinkEndMatch.index + 8 // After </think>
            } else {
                // No closing tag found, treat as regular content
                parts.push({
                    type: 'markdown',
                    content: content.slice(currentPos)
                })
                break
            }
        }

        // Add any remaining content
        if (currentPos < content.length) {
            parts.push({
                type: 'markdown',
                content: content.slice(currentPos)
            })
        }

        return parts
    }

    const parts = parseThinkingContent(children)

    return (
        <div>
            {parts.map((part, index) => {
                if (part.type === 'thinking') {
                    return (
                        <div key={index} className="thinking-section">
                            <span className="thinking-label">Thinking</span>
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                    code: ({ inline, className, children, ...props }) => (
                                        <CodeBlock inline={inline} className={className} {...props}>
                                            {children}
                                        </CodeBlock>
                                    ),
                                    // Make sure thinking content doesn't have extra margins
                                    p: ({ children }) => <p style={{ margin: '0.25rem 0' }}>{children}</p>
                                }}
                            >
                                {part.content}
                            </ReactMarkdown>
                        </div>
                    )
                } else {
                    return (
                        <ReactMarkdown
                            key={index}
                            remarkPlugins={[remarkGfm]}
                            components={{
                                code: ({ inline, className, children, ...props }) => (
                                    <CodeBlock inline={inline} className={className} {...props}>
                                        {children}
                                    </CodeBlock>
                                )
                            }}
                        >
                            {part.content}
                        </ReactMarkdown>
                    )
                }
            })}
        </div>
    )
}

export default ThinkingMarkdown
