import "./icp.css";
import { Link } from "react-router-dom";

function IdealCustomerProfile() {
  return (
    <div
      id="icp-instructions-div"
      className="container d-flex flex-column m-3 p-3"
    >
      <div>
        <p>
          You can create the Ideal Customer Profile (ICPs) and Personas used for
          your outbound efforts.
        </p>
        <p>
          Multiple ICPs can be created and each one can be used in a different
          campaign.
        </p>
        <p>ICP configurations can also be edited at any time.</p>
      </div>
      <div className="d-flex justify-content-start">
        <Link to="/icp/create">
          <button type="button" className="mt-2">
            Create new ICP
          </button>
        </Link>
      </div>
    </div>
  );
}

export default IdealCustomerProfile;
