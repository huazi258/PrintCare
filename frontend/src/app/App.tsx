import { BrowserRouter } from "react-router-dom";
import { AppErrorBoundary } from "@/components/AppErrorBoundary";
import { AppRoutes } from "@/app/routes";

export function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppErrorBoundary>
  );
}
