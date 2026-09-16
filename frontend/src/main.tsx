import React from "react";
import { createRoot } from "react-dom/client";
import { Dashboard } from "./pages/Dashboard";
import { DbtFailurePipeline } from "./pages/DbtFailurePipeline";
import "./style.css";

const page = window.location.pathname === "/pipeline" ? <DbtFailurePipeline /> : <Dashboard />;
createRoot(document.getElementById("root")!).render(<React.StrictMode>{page}</React.StrictMode>);
