import React, { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import StreamingMonaco from './StreamingMonaco'

function computeStreamingSegments(text) {
    // Pick the last fenced block (open or closed) near the end
    const openRe = /```([a-zA-Z0-9_-]+)?\n/g
    const positions = []
    let m
    while ((m = openRe.exec(text)) !== null) {
        positions.push({ i: m.index, lang: m[1] || 'plaintext', len: m[0].length })
    }
    if (positions.length === 0) return { before: text, code: null, lang: null, after: '' }
    const last = positions[positions.length - 1]
    const afterOpen = text.slice(last.i + last.len)
    const relClose = afterOpen.indexOf('```')
    const codeEnd = relClose === -1 ? text.length : last.i + last.len + relClose
    const before = text.slice(0, last.i)
    const code = text.slice(last.i + last.len, codeEnd)
    const after = relClose === -1 ? '' : text.slice(codeEnd + 3)
    return { before, code, lang: last.lang, after }
}

const LANG_WHITELIST = new Set([
    'javascript', 'typescript', 'js', 'ts', 'jsx', 'tsx', 'python', 'py', 'go', 'rust', 'rs', 'c', 'cpp', 'c++', 'java', 'kotlin', 'swift', 'php', 'ruby', 'rb', 'r', 'bash', 'sh', 'zsh', 'powershell', 'ps1', 'shell', 'sql', 'yaml', 'yml', 'json', 'toml', 'ini', 'dockerfile', 'gradle', 'xml', 'html', 'css', 'scss', 'less'
])

function splitCodeAndTrailingProse(code) {
    if (!code) return [code, '']
    const idx = code.lastIndexOf('\n\n')
    if (idx === -1) return [code, '']
    const trailing = code.slice(idx + 2)
    const firstLine = trailing.split('\n')[0]?.trim() || ''
    const proseStart = /^(Note|Explanation|In this|Summary|Output|Result|This example)/i.test(firstLine) || /^[-*]\s+/.test(firstLine) || /^\d+\.\s+/.test(firstLine) || (/^[A-Z][a-z]/.test(firstLine) && firstLine.split(' ').length >= 3)
    const symbolDensity = (trailing.match(/[{}();=<>]/g) || []).length / (trailing.length || 1)
    const hasFence = trailing.includes('```')
    if (hasFence) return [code, '']
    if (proseStart && symbolDensity < 0.03) {
        return [code.slice(0, idx), trailing]
    }
    return [code, '']
}

function StreamingMarkdownImpl({ text }) {
    const { before, code, lang, after } = useMemo(() => computeStreamingSegments(text || ''), [text])

    return (
        <div className="md max-w-none">
            {before && (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {before}
                </ReactMarkdown>
            )}
            {(code !== null) && (() => {
                const theLang = String(lang || 'plaintext').toLowerCase()
                const hasMultipleLines = /\n/.test(code)
                const isAllowed = hasMultipleLines && LANG_WHITELIST.has(theLang)

                // Split out trailing prose if detected
                const [codePart, trailing] = splitCodeAndTrailingProse(code)
                return (
                    <>
                        <StreamingMonaco language={isAllowed ? theLang : 'plaintext'} value={codePart} />
                        {(trailing || after) && (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{`${trailing}${after}`}</ReactMarkdown>
                        )}
                    </>
                )
            })()}
            {code === null && after && (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{after}</ReactMarkdown>
            )}
        </div>
    )
}

const StreamingMarkdown = memo(StreamingMarkdownImpl, (prev, next) => prev.text === next.text)
export default StreamingMarkdown


