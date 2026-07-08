import React from "react";
import "./App.css";
// Load shared UI primitives (and their styles) eagerly so their CSS has a
// stable order in the main chunk instead of per-lazy-chunk orderings.
import "shared/components/ui";
import { BrowserRouter as Router } from "react-router-dom";
import { AppProviders, SessionExpiredHandler } from "app/providers";
import AppRoutes from "app/routes";

function App() {
  return (
    <AppProviders>
      <Router>
        <SessionExpiredHandler />
        <AppRoutes />
      </Router>
    </AppProviders>
  );
}

export default App;
