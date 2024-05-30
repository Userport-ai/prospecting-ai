import "./App.css";
import { GiArchiveResearch } from "react-icons/gi";
import { IoHomeOutline } from "react-icons/io5";
import { MdDashboard, MdCampaign } from "react-icons/md";
import { FaRegBuilding } from "react-icons/fa";
import { CiLogout } from "react-icons/ci";

function App() {
  return (
    <>
      <div id="sidebar" className="container-fluid">
        <nav className="navbar d-flex flex-column justify-content-start">
          <a href="#" className="navbar-brand">
            <GiArchiveResearch />
            <span>Prospecting AI</span>
          </a>
          <hr />
          <div className="container ps-4">
            <ul className="navbar-nav">
              <li className="nav-item d-flex flex-row mt-4">
                <IoHomeOutline className="nav-icon" />
                <div className="nav-text">Home</div>
              </li>
              <li className="nav-item d-flex flex-row mt-4">
                <MdDashboard className="nav-icon" />
                <div className="nav-text">ICP</div>
              </li>
              <li className="nav-item d-flex flex-row mt-4">
                <MdCampaign className="nav-icon" />
                <div className="nav-text">Campaigns</div>
              </li>
              <li className="nav-item d-flex flex-row mt-4">
                <FaRegBuilding className="nav-icon" />
                <div className="nav-text">Accounts</div>
              </li>
            </ul>
          </div>
          <div
            id="logout-container"
            className="container mt-auto d-flex flex-column"
          >
            <hr />
            <a href="#" className="mb-3">
              <CiLogout id="icon" />
              <span>Logout</span>
            </a>
          </div>
        </nav>
      </div>
      <div id="details" className="container-fluid"></div>
    </>
  );
}

export default App;
