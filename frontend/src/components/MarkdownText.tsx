import { Fragment, type ReactNode } from 'react'

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    return <Fragment key={index}>{part}</Fragment>
  })
}

export function MarkdownText({ text, className = '' }: { text: string; className?: string }) {
  if (!text) return null
  const blocks = text.replace(/\r\n/g, '\n').split(/\n{2,}/)

  return (
    <div className={`prose ${className}`}>
      {blocks.map((block, index) => {
        const trimmed = block.trim()
        if (!trimmed) return null

        if (trimmed.startsWith('## ')) {
          return <h2 key={index}>{trimmed.slice(3)}</h2>
        }
        if (trimmed.startsWith('### ')) {
          return <h3 key={index}>{trimmed.slice(4)}</h3>
        }

        const lines = trimmed.split('\n')
        if (lines.every((line) => /^[•\-]\s/.test(line.trim()))) {
          return (
            <ul key={index}>
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{inline(line.trim().replace(/^[•\-]\s/, ''))}</li>
              ))}
            </ul>
          )
        }
        if (lines.every((line) => /^\d+\.\s/.test(line.trim()))) {
          return (
            <ol key={index}>
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{inline(line.trim().replace(/^\d+\.\s/, ''))}</li>
              ))}
            </ol>
          )
        }

        return <p key={index}>{inline(lines.join(' '))}</p>
      })}
    </div>
  )
}
