import "./App.css";
import Sidebar from "./Sidebar";
import { Outlet } from "react-router-dom";

function App() {
  return (
    <>
      {/* We need container-fluid class to ensure full screen width is taken. */}
      <div className="container-fluid d-flex p-0">
        <Sidebar />
        {/* We need container-fluid class to remaining screen width for the app is fully taken. */}
        <div
          id="app-div"
          className="container-fluid d-flex justify-content-start p-0"
        >
          <Outlet />
        </div>
      </div>
    </>
  );
}

export default App;
