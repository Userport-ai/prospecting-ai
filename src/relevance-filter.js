import { useState } from "react";
import "./relevance-filter.css";
import { Button, CloseButton, Form, InputGroup } from "react-bootstrap";

function RaisedFunding() {
  return (
    <div
      id="raised-funding-container"
      className="container d-flex flex-row justify-content-start mt-3 p-0"
    >
      <p>In the last </p>
      <Form.Select className="ms-3">
        <option value="none" selected></option>
        <option value="3m">3 months</option>
        <option value="6m">6 months</option>
        <option value="12m">12 months</option>
      </Form.Select>
    </div>
  );
}

function IsHiring() {
  return (
    <div
      id="is-hiring-container"
      className="container d-flex flex-column mt-3 p-0"
    >
      <div className="container d-flex flex-row p-0 is-hiring-inputs">
        <p>Function</p>
        <Form.Select className="ms-3">
          <option value="any" selected>
            Any
          </option>
          <option value="sales">Sales</option>
          <option value="marketing">Marketing</option>
          <option value="engineering">Engineering</option>
          <option value="product">Product</option>
          <option value="HR">HR</option>
          <option value="IT">IT</option>
        </Form.Select>
      </div>
      <div className="container d-flex flex-row p-0 is-hiring-inputs">
        <p>Role</p>
        <Form.Select className="ms-3">
          <option value="any" selected>
            Any
          </option>
          <option value="sdr">Sales Development Representative</option>
          <option value="ae">Account Executive</option>
          <option value="eng-manager">Engineering Manager</option>
        </Form.Select>
      </div>
    </div>
  );
}

function CustomerChip({ customerName }) {
  return (
    <div className="customer-chip d-flex flex-row p-2 ms-2">
      <div id="customer-name">{customerName}</div>
      <CloseButton />
    </div>
  );
}

function SimilarToCustomers() {
  const [customers, setCustomers] = useState(["glean.com", "Hubspot"]);

  function handleClick() {}

  return (
    <div
      id="similar-customers-container"
      className="container d-flex flex-column align-items-start p-0"
    >
      <div
        id="similar-customers-input"
        className="container d-flex flex-row mt-3 p-0"
      >
        <InputGroup>
          <Form.Control type="text" placeholder="Enter company" />
          <Button variant="primary" onClick={handleClick}>
            +
          </Button>
        </InputGroup>
      </div>
      <div
        id="similar-customers-display"
        className="container d-flex flex-row mt-2 p-0"
      >
        <div id="similar-to-text" className="p-2">
          Similar to:
        </div>
        {customers.map((customerName) => (
          <CustomerChip customerName={customerName} />
        ))}
      </div>
    </div>
  );
}

function RelevanceFilterInputs({ filterId }) {
  switch (filterId) {
    case "raised-funding-recently":
      return <RaisedFunding />;
    case "hiring-recently":
      return <IsHiring />;
    case "similar-to-customers":
      return <SimilarToCustomers />;
    default:
      return null;
  }
}

export default RelevanceFilterInputs;
