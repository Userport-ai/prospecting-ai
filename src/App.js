import Sidebar from "./Sidebar";
import { Outlet } from "react-router-dom";

function App() {
  return (
    <>
      <Sidebar />
      <div id="detail">
        <Outlet />
      </div>
    </>
  );
}

export default App;
