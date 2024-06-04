import "./create-icp.css";
import { Accordion, Button, Form, CloseButton, Card } from "react-bootstrap";
import RelevanceFilterInputs from "./relevance-filter";
import { useState } from "react";

function RelevanceFilter() {
  const [filterId, setFilterId] = useState("none");

  function handleValueChange(e) {
    let gotFilterId = e.target.value;
    setFilterId(gotFilterId);
  }

  return (
    <Card className="mt-3">
      <Card.Body>
        <div
          id="relevance-fitler-container"
          className="container d-flex flex-row justify-content-between"
        >
          <Form.Select size="sm" className="w-90" onChange={handleValueChange}>
            <option value="none"></option>
            <option value="raised-funding-recently">
              Have they raised money recently?
            </option>
            <option value="hiring-recently">
              Have they started hiring recently?
            </option>
            <option value="similar-to-customers">
              Are they similar to current customers in the same vertical?
            </option>
            <option value="using-competitors">
              Are they using any of our competitors today?
            </option>
            <option value="using-technologies">
              Are they using these specific technologies in their stack?
            </option>
            <option value="acquired-company-recently">
              Have they acquired any companies recently?
            </option>
            <option value="new-leadership-joined-recently">
              Has a new leader joined the company recently?
            </option>
            <option value="planning-launch-to-new-market">
              Have they recently announced plans to enter a new market?
            </option>
            <option value="product-announcement">
              Have they announced the launch of a new product?
            </option>
            <option value="got-acquired-recently">
              Have they been acquired recently?
            </option>
          </Form.Select>
          <CloseButton size="sm" />
        </div>
        <RelevanceFilterInputs filterId={filterId} />
      </Card.Body>
    </Card>
  );
}

function CreateICP() {
  function handleAddRevelanceFilter() {
    console.log("Testing that relevance works!");
  }

  return (
    <div className="d-flex flex-row justify-content-center">
      <div id="create-icp" className="d-flex flex-column mt-5 pb-3">
        <div
          id="account-profile-title"
          className="create-icp-filter container d-flex justify-content-center mt-2 mb-2"
        >
          <p>Account Profile</p>
        </div>
        <div className="create-icp-filter filters-title container mt-2">
          <p>Standard Filters</p>
        </div>
        <div className="create-icp-filter container d-flex flex-column">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="industry">
              <Accordion.Header>Industry</Accordion.Header>
              <Accordion.Body>
                <Form.Select size="sm">
                  <option value="none">N/A</option>
                  <option value="Saas">SaaS</option>
                  <option value="Real Estate">Real Estate</option>
                  <option value="Banking">Banking</option>
                  <option value="Media">Media & Entertainment</option>
                </Form.Select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="region">
              <Accordion.Header>Region</Accordion.Header>
              <Accordion.Body>
                <Form.Select size="sm">
                  <option value="none">N/A</option>
                  <option value="AMER">AMER</option>
                  <option value="EMEA">EMEA</option>
                  <option value="APAC">APAC</option>
                </Form.Select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="company-headcount">
              <Accordion.Header>Company Headcount</Accordion.Header>
              <Accordion.Body>
                <Form.Select size="sm">
                  <option value="none">N/A</option>
                  <option value="1-10">1-10</option>
                  <option value="10-50">10-50</option>
                  <option value="50-100">50-100</option>
                </Form.Select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>
        <div className="create-icp-filter container d-flex flex-column mt-4">
          <Accordion alwaysOpen>
            <Accordion.Item eventKey="function-headcount">
              <Accordion.Header>Function Headcount</Accordion.Header>
              <Accordion.Body>
                <Form.Select size="sm">
                  <option value="none">Function Name</option>
                  <option value="Marketing">Marketing</option>
                  <option value="Sales">Sales</option>
                  <option value="Engineering">Engineering</option>
                  <option value="IT">IT</option>
                  <option value="HR">HR</option>
                </Form.Select>
                <Form.Select size="sm" className="mt-2">
                  <option>N/A</option>
                  <option value="1-5">1-5</option>
                  <option value="1-10">1-10</option>
                  <option value="1-20">1-20</option>
                  <option value="1-30">1-30</option>
                  <option value="1-40">1-40</option>
                </Form.Select>
              </Accordion.Body>
            </Accordion.Item>
          </Accordion>
        </div>

        <div className="create-icp-filter filters-title container mt-5">
          <p>Relevance Filters</p>
        </div>
        <div
          id="relevance-btn"
          className="create-icp-filter container d-flex flex-column"
        >
          <Button onClick={handleAddRevelanceFilter}>Add filter</Button>
          <RelevanceFilter />
        </div>
      </div>
    </div>
  );
}

export default CreateICP;
