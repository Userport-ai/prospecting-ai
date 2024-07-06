import "./App.css";
import { Layout } from "antd";
import AppHeader from "./app-header";
import { Outlet } from "react-router-dom";

const { Content } = Layout;

function App() {
  return (
    <>
      <div id="app-container">
        <AppHeader></AppHeader>
        <Content>
          <Outlet></Outlet>
        </Content>
      </div>
    </>
  );
}

export default App;
