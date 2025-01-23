import { APIProvider } from "@vis.gl/react-google-maps";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import Dashboard from "./Dashboard";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <APIProvider apiKey={import.meta.env.VITE_GOOGLE_MAPS_API_KEY}>
      <Dashboard />
    </APIProvider>
  </StrictMode>,
);
