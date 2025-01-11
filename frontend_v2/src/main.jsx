import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App.jsx";
import Playbook from "./playbook/Playbook";
import AddProduct from "./playbook/AddProduct";
import ProductsPage from "./playbook/ProductsPage";
import Accounts from "./accounts/Accounts";
import { Login } from "./auth/Login";
import { SignUp } from "./auth/SignUp";
import AuthProvider from "./auth/AuthProvider";
import Leads from "./leads/Leads";

createRoot(document.getElementById("root")).render(
  <StrictMode>
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
            <Route path="accounts" element={<Accounts />}></Route>
            <Route path="leads" element={<Leads />}></Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>
);
