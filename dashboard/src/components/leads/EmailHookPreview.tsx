"use client"

interface EmailHookPreviewProps {
  hook: string
  className?: string
}

export function EmailHookPreview({ hook, className }: EmailHookPreviewProps) {
  return (
    <div className={className}>
      <p className="text-xs leading-relaxed text-foreground/80">
        💡 &ldquo;{hook}&rdquo;
      </p>
    </div>
  )
}
