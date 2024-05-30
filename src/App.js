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
              <li className="nav-item">
                <a href="#" className="nav-link">
                  <IoHomeOutline className="nav-icon" />
                  <div className="nav-text">Home</div>
                </a>
              </li>
              <li className="nav-item">
                <a href="#" className="nav-link">
                  <MdDashboard className="nav-icon" />
                  <div className="nav-text">ICP</div>
                </a>
              </li>
              <li className="nav-item">
                <a href="#" className="nav-link">
                  <MdCampaign className="nav-icon" />
                  <div className="nav-text">Campaigns</div>
                </a>
              </li>
              <li className="nav-item">
                <a href="#" className="nav-link">
                  <FaRegBuilding className="nav-icon" />
                  <div className="nav-text">Accounts</div>
                </a>
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
