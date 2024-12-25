import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App.jsx";
import Playbook from "./playbook/Playbook";
import AddProduct from "./playbook/AddProduct";
import ProductsPage from "./playbook/ProductsPage";
import Accounts from "./accounts/Accounts";
import { LoginForm } from "./auth/LoginForm";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginForm />} />
        <Route path="/" element={<App />}>
          <Route path="playbook" element={<Playbook />}>
            <Route index element={<ProductsPage />} />
            <Route path="add-product" element={<AddProduct />} />
          </Route>
          <Route path="accounts" element={<Accounts />}></Route>
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
