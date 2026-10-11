import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "@/components/FeedbackState";

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  hasError: boolean;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  public state: AppErrorBoundaryState = { hasError: false };

  public static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("应用渲染失败", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <main className="mx-auto max-w-6xl px-4 py-8">
          <ErrorState message="页面渲染时发生错误。请刷新页面后重试。" />
        </main>
      );
    }

    return this.props.children;
  }
}
