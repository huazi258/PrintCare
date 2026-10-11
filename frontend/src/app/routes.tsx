import { Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { AdminPage } from "@/pages/AdminPage";
import { DiagnosisPage } from "@/pages/DiagnosisPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { QaPage } from "@/pages/QaPage";
import { WorkbenchPage } from "@/pages/WorkbenchPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<WorkbenchPage />} />
        <Route path="qa" element={<QaPage />} />
        <Route path="diagnosis" element={<DiagnosisPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
