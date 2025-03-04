import { ErrorInfo, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import "./index.css";
import App from "./App.jsx";
import Playbook from "./playbook/Playbook";
import AddProduct from "./playbook/AddProduct";
import ProductsPage from "./playbook/ProductsPage";
import AccountsTable from "./accounts/AccountsTable.js";
import { Login } from "./auth/Login";
import { SignUp } from "./auth/SignUp";
import AuthProvider from "./auth/AuthProvider";
import { ErrorBoundary } from "react-error-boundary";
import { ErrorFallback } from "./ErrorFallback.js";
import LeadsInAccountV2 from "./accounts/LeadsInAccountV2.js";
import AccountsView from "./accounts/AccountsView.js";
import LeadsView from "./leads/LeadsView.js";
import EditProduct from "./playbook/EditProduct.js";

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
              <Route index element={<Navigate to="/accounts" replace />} />{" "}
              {/* Redirect / to /accounts */}
              <Route path="products" element={<Playbook />}>
                <Route index element={<ProductsPage />} />
                <Route path="add" element={<AddProduct />} />
                <Route path="edit/:id" element={<EditProduct />} />
              </Route>
              <Route path="accounts" element={<AccountsView />}>
                <Route index element={<AccountsTable />} />
                <Route path=":id/leads" element={<LeadsInAccountV2 />} />
              </Route>
              <Route path="leads" element={<LeadsView />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  </StrictMode>
);
