interface FeedbackStateProps {
  message: string;
}

export function LoadingState({ message = "正在加载…" }: Partial<FeedbackStateProps>) {
  return (
    <p aria-live="polite" className="rounded-md border border-border bg-muted px-4 py-3 text-sm text-muted-foreground">
      {message}
    </p>
  );
}

export function ErrorState({ message }: FeedbackStateProps) {
  return (
    <p aria-live="assertive" className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {message}
    </p>
  );
}
