import { ErrorInfo, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App.jsx";
import Playbook from "./playbook/Playbook";
import AddProduct from "./playbook/AddProduct";
import ProductsPage from "./playbook/ProductsPage";
import AccountsTable from "./accounts/AccountsTable.js";
import { Login } from "./auth/Login";
import { SignUp } from "./auth/SignUp";
import AuthProvider from "./auth/AuthProvider";
import LeadsTable from "./leads/LeadsTable.js";
import { ErrorBoundary } from "react-error-boundary";
import { ErrorFallback } from "./ErrorFallback.js";
import LeadsInAccountTable from "./accounts/LeadsInAccountTable.js";

// Error Logging Function
function logErrorToService(error: Error, info: ErrorInfo) {
  // Log error to server.
  console.error("Error in React app: ", error, " with info: ", info);
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onError={logErrorToService}
    >
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<SignUp />} />
            <Route path="/" element={<App />}>
              <Route path="playbook" element={<Playbook />}>
                <Route index element={<ProductsPage />} />
                <Route path="add-product" element={<AddProduct />} />
              </Route>
              <Route path="accounts" element={<AccountsTable />} />
              <Route
                path="accounts/:id/leads"
                element={<LeadsInAccountTable />}
              />
              <Route path="leads" element={<LeadsTable />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  </StrictMode>
);
