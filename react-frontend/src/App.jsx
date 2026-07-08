import React from "react";
import "./App.css";
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
