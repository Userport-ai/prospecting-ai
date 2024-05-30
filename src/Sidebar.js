import "./App.css";
import { GiArchiveResearch } from "react-icons/gi";
import { IoHomeOutline } from "react-icons/io5";
import { MdDashboard, MdCampaign } from "react-icons/md";
import { FaRegBuilding } from "react-icons/fa";
import { CiLogout } from "react-icons/ci";

function NavItem({ text, children }) {
  return (
    <li key={text} className="nav-item">
      <a href="#" className="nav-link">
        {children}
        <div className="nav-text">{text}</div>
      </a>
    </li>
  );
}

function Sidebar() {
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
              <NavItem text="Home">
                <IoHomeOutline className="nav-icon" />
              </NavItem>
              <NavItem text="ICP">
                <MdDashboard className="nav-icon" />
              </NavItem>
              <NavItem text="Campaigns">
                <MdCampaign className="nav-icon" />
              </NavItem>
              <NavItem text="Accounts">
                <FaRegBuilding className="nav-icon" />
              </NavItem>
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
    </>
  );
}

export default Sidebar;
