import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

interface MarkdownRendererProps {
  content: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        ol: ({ children }) => (
          <ol
            style={{
              paddingLeft: "1rem",
              marginTop: "1rem",
              listStyleType: "decimal",
            }}
          >
            {children}
          </ol>
        ),
        ul: ({ children }) => (
          <ul style={{ paddingLeft: "1rem", listStyleType: "disc" }}>
            {children}
          </ul>
        ),
        li: ({ children }) => (
          <li style={{ marginBottom: "1rem" }}>{children}</li>
        ), // Add spacing between items
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "blue", textDecoration: "underline" }}
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
};

export default MarkdownRenderer;
