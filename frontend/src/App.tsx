import { lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Join from "./pages/Join";
import Layout from "./components/Layout";
import { Toaster } from "./components/ui";
import { useAuth } from "./lib/auth";
import Login from "./pages/Login";
const Projects = lazy(() => import("./pages/Projects"));  // loaded only when opened
const Settings = lazy(() => import("./pages/Settings"));  // loaded only when opened
const EstimatePage = lazy(() => import("./pages/Estimate"));  // loaded only when opened
const DesignPage = lazy(() => import("./pages/Design"));  // loaded only when opened
const VastuPage = lazy(() => import("./pages/Vastu"));  // loaded only when opened
const SitePage = lazy(() => import("./pages/Site"));  // loaded only when opened
const AIPage = lazy(() => import("./pages/AI"));  // loaded only when opened
import { HomePage } from "./pages/Modules";

export default function App() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loc.pathname.startsWith("/join/")) return <Join token={loc.pathname.slice(6).split("/")[0]} />;  // invite link (no login)
  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-slate-500">Loading Nexora Build…</div>;
  }
  return (
    <>
      <Toaster />
      {!user ? (
        <Routes><Route path="*" element={<Login />} /></Routes>
      ) : (
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="projects" element={<Projects />} />
            <Route path="design" element={<DesignPage />} />
            <Route path="site" element={<SitePage />} />
            <Route path="vastu" element={<VastuPage />} />
            <Route path="estimate" element={<EstimatePage />} />
            <Route path="ai" element={<AIPage />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      )}
    </>
  );
}
