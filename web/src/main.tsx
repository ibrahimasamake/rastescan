import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
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
const Queue = lazy(() => import("./officer/Queue"));
const Review = lazy(() => import("./officer/Review"));
const Team = lazy(() => import("./officer/Team"));
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

// Hash routing works the same on the web, inside the Android app, and behind CloudFront.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <PortalProvider>
        <HashRouter>
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
                <Route path="/about" element={<Static.About />} />
                <Route path="/privacy" element={<Static.Privacy />} />
                <Route path="/accessibility" element={<Static.Accessibility />} />
                <Route path="/open-data" element={<Static.OpenData />} />
                <Route path="/officer" element={<Queue />} />
                <Route path="/officer/review" element={<Review />} />
                <Route path="/officer/team" element={<Team />} />
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
