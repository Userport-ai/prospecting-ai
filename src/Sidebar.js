import "./sidebar.css";
import { Link } from "react-router-dom";
import { GiArchiveResearch } from "react-icons/gi";
import { IoHomeOutline } from "react-icons/io5";
import { MdDashboard, MdCampaign } from "react-icons/md";
import { FaRegBuilding } from "react-icons/fa";
import { CiLogout } from "react-icons/ci";

function NavItem({ url, text, children }) {
  return (
    <li key={text} className="nav-item">
      <Link to={url} className="nav-link">
        {children}
        <div className="nav-text">{text}</div>
      </Link>
    </li>
  );
}

function Sidebar() {
  return (
    <>
      <div id="sidebar" className="container">
        <nav className="navbar d-flex flex-column justify-content-start">
          <a href="#" className="navbar-brand">
            <GiArchiveResearch />
            <span>Prospecting AI</span>
          </a>
          <hr />
          <div className="container ps-4">
            <ul className="navbar-nav">
              <NavItem url="/" text="Home">
                <IoHomeOutline className="nav-icon" />
              </NavItem>
              <NavItem url="icp" text="ICP">
                <MdDashboard className="nav-icon" />
              </NavItem>
              <NavItem url="camp" text="Campaigns">
                <MdCampaign className="nav-icon" />
              </NavItem>
              <NavItem url="accounts" text="Accounts">
                <FaRegBuilding className="nav-icon" />
              </NavItem>
            </ul>
          </div>
          <div id="logout-container">
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
