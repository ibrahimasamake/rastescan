import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Report from "./pages/Report";
import "./styles.css";

// Hash routing works the same on the web, inside the Android app, and behind CloudFront.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <Routes>
        <Route path="/" element={<Report />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="*" element={<Report />} />
      </Routes>
    </HashRouter>
  </StrictMode>,
);
