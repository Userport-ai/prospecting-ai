import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router";
import "./index.css";
import App from "./App.jsx";
import Playbook from "./playbook/Playbook";
import AddProduct from "./playbook/AddProduct";
import ListProducts from "./playbook/ListProducts";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route path="playbook" element={<Playbook />}>
            <Route index element={<ListProducts />} />
            <Route path="add-product" element={<AddProduct />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
