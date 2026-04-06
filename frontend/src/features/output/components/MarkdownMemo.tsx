import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import rehypeSlug from 'rehype-slug'

// Extend default sanitize schema to allow GFM table elements and heading IDs
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames ?? []),
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'tfoot',
    'caption',
  ],
  attributes: {
    ...defaultSchema.attributes,
    '*': [...(defaultSchema.attributes?.['*'] ?? []), 'id', 'className'],
    th: ['align'],
    td: ['align'],
  },
}

interface Props {
  content: string
}

export function MarkdownMemo({ content }: Props) {
  return (
    <article className="prose prose-zinc max-w-none dark:prose-invert font-body text-[16px] leading-[1.5]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema], rehypeSlug]}
        components={{
          h1: ({ children, id }) => (
            <h1 id={id} className="font-display text-[28px] mt-[24px] mb-[16px]">
              {children}
            </h1>
          ),
          h2: ({ children, id }) => (
            <h2 id={id} className="font-display text-[20px] mt-[16px] mb-[8px]">
              {children}
            </h2>
          ),
          h3: ({ children, id }) => (
            <h3 id={id} className="font-display text-[20px] mt-[16px] mb-[8px]">
              {children}
            </h3>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-primary underline focus:ring-2 focus:ring-ring"
              target="_blank"
              rel="noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  )
}
