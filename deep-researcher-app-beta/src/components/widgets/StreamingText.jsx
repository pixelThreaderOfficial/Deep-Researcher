import React from 'react'
import { motion } from 'framer-motion'

// StreamingText: render the full text in one flow to avoid spacing artifacts.
// Keeps whitespace and newlines intact with CSS from parent (use whitespace-pre-wrap).
export default function StreamingText({ text = '', className = '' }) {
    return (
        <motion.span
            className={className}
            initial={{ opacity: 0.3 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.15 }}
        >
            {text}
        </motion.span>
    )
}


