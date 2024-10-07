import "./App.css";
import { Layout } from "antd";
import AppHeader from "./app-header";
import { Navigate, Outlet } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "./root";

const { Content } = Layout;

function App() {
  const { user } = useContext(AuthContext);

  if (!user) {
    // User is logged out, redirect to login page.
    return <Navigate to="/login" replace />;
  }

  // User is logged in, display app.
  return (
    <>
      <div id="app-container">
        <AppHeader></AppHeader>
        <Content>
          <Outlet />
        </Content>
      </div>
    </>
  );
}

export default App;
