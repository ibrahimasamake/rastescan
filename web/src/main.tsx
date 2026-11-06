import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import IntroVideo from "./components/IntroVideo";
import { Layout } from "./components/Layout";
import { Skeleton } from "./components/States";
import { I18nProvider } from "./i18n";
import Home from "./pages/Home";
import { PortalProvider } from "./portal";
import "./styles.css";

// Everything except the home page loads on demand, so a phone on a slow network gets the first screen quickly.
const ReportPage = lazy(() => import("./pages/ReportPage"));
const NewReport = lazy(() => import("./pages/NewReport"));
const MyReports = lazy(() => import("./pages/MyReports"));
const MapPage = lazy(() => import("./pages/MapPage"));
const ListPage = lazy(() => import("./pages/ListPage"));
const Wards = lazy(() => import("./pages/Wards"));
const Impact = lazy(() => import("./pages/Impact"));
const Queue = lazy(() => import("./officer/Queue"));
const Review = lazy(() => import("./officer/Review"));
const Team = lazy(() => import("./officer/Team"));
const Models = lazy(() => import("./officer/Models"));
const Analytics = lazy(() => import("./officer/Analytics"));
const WorkOrder = lazy(() => import("./officer/WorkOrder"));
const Static = {
  About: lazy(() => import("./pages/Static").then((m) => ({ default: m.About }))),
  Privacy: lazy(() => import("./pages/Static").then((m) => ({ default: m.Privacy }))),
  Accessibility: lazy(() => import("./pages/Static").then((m) => ({ default: m.Accessibility }))),
  OpenData: lazy(() => import("./pages/Static").then((m) => ({ default: m.OpenData }))),
  NotFound: lazy(() => import("./pages/Static").then((m) => ({ default: m.NotFound }))),
};

function Loading() {
  return <div className="wrap page"><Skeleton h={36} w="40%" /><Skeleton h={240} /></div>;
}

// Offline support: cache the app shell, the last public data and photos. Production builds only.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
}

// Hash routing works the same on the web, inside the Android app, and behind CloudFront.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <PortalProvider>
        <HashRouter>
          <IntroVideo />
          <Layout>
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/report" element={<NewReport />} />
                <Route path="/r/:code" element={<ReportPage />} />
                <Route path="/mine" element={<MyReports />} />
                <Route path="/map" element={<MapPage />} />
                <Route path="/reports" element={<ListPage />} />
                <Route path="/wards" element={<Wards />} />
                <Route path="/impact" element={<Impact />} />
                <Route path="/about" element={<Static.About />} />
                <Route path="/privacy" element={<Static.Privacy />} />
                <Route path="/accessibility" element={<Static.Accessibility />} />
                <Route path="/open-data" element={<Static.OpenData />} />
                <Route path="/officer" element={<Queue />} />
                <Route path="/officer/review" element={<Review />} />
                <Route path="/officer/team" element={<Team />} />
                <Route path="/officer/models" element={<Models />} />
                <Route path="/officer/analytics" element={<Analytics />} />
                <Route path="/officer/work-order" element={<WorkOrder />} />
                <Route path="/dashboard" element={<Navigate to="/officer" replace />} />
                <Route path="*" element={<Static.NotFound />} />
              </Routes>
            </Suspense>
          </Layout>
        </HashRouter>
      </PortalProvider>
    </I18nProvider>
  </StrictMode>,
);
