import { Accordion } from "react-bootstrap";
import "./create-icp.css";
function CreateICP() {
  return (
    <div className="d-flex justify-content-center">
      <div id="create-icp" className="d-flex flex-column mt-5 pb-5">
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="industry">
              <Accordion.Header>Industry</Accordion.Header>
              <Accordion.Body>
                <select className="form-select-sm">
                  <option selected>N/A</option>
                  <option value="Saas">SaaS</option>
                  <option value="Real Estate">Real Estate</option>
                  <option value="Banking">Banking</option>
                  <option value="Media">Media & Entertainment</option>
                </select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="region">
              <Accordion.Header>Region</Accordion.Header>
              <Accordion.Body>
                <select className="form-select-sm">
                  <option selected>N/A</option>
                  <option value="AMER">AMER</option>
                  <option value="EMEA">EMEA</option>
                  <option value="APAC">APAC</option>
                </select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="company-headcount">
              <Accordion.Header>Company Headcount</Accordion.Header>
              <Accordion.Body>
                <select className="form-select-sm">
                  <option selected>N/A</option>
                  <option value="1-10">1-10</option>
                  <option value="10-50">10-50</option>
                  <option value="50-100">50-100</option>
                </select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="function-headcount">
              <Accordion.Header>Function Headcount</Accordion.Header>
              <Accordion.Body>
                <select className="form-select-sm">
                  <option selected>Function Name</option>
                  <option value="Marketing">Marketing</option>
                  <option value="Sales">Sales</option>
                  <option value="Engineering">Engineering</option>
                  <option value="IT">IT</option>
                  <option value="HR">HR</option>
                </select>
                <select className="form-select-sm mt-2">
                  <option selected>N/A</option>
                  <option value="1-5">1-5</option>
                  <option value="1-10">1-10</option>
                  <option value="1-20">1-20</option>
                  <option value="1-30">1-30</option>
                  <option value="1-40">1-40</option>
                </select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
      </div>
    </div>
  );
}

export default CreateICP;
