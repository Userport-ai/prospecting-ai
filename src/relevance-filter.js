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
        <option value="none"></option>
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
          <option value="any">Any</option>
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
          <option value="any">Any</option>
          <option value="sdr">Sales Development Representative</option>
          <option value="ae">Account Executive</option>
          <option value="eng-manager">Engineering Manager</option>
        </Form.Select>
      </div>
    </div>
  );
}

function CustomerChip({ customerName, onClose }) {
  function handleClose(e) {
    e.stopPropagation();
    onClose(customerName);
  }
  return (
    <div className="customer-chip d-flex flex-row flex-wrap p-2 ms-2">
      <div id="customer-name">{customerName}</div>
      <CloseButton onClick={handleClose} />
    </div>
  );
}

/**
 * Allows users to manually enter customers they think are similar.
 * TODO: Get company list from backend API instead of letting user type
 * which is more error prone.
 */
function SimilarToCustomers() {
  const [customerNames, setCustomerNames] = useState([]);
  const [currentCustomerName, setCurrentCustomerName] = useState("");

  function handleCustomerNameChange(e) {
    e.stopPropagation();
    let customerName = e.target.value;
    setCurrentCustomerName(customerName);
  }

  function handleCustomerNameSubmitted(e) {
    e.stopPropagation();
    if (
      currentCustomerName !== "" &&
      !customerNames.includes(currentCustomerName)
    ) {
      // Add to customer name list.
      setCustomerNames([...customerNames, currentCustomerName]);
      setCurrentCustomerName("");
    }
  }

  function handleChipRemoval(customerName) {
    setCustomerNames(customerNames.filter((name) => name !== customerName));
  }

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
          <Form.Control
            type="text"
            placeholder="Enter company"
            onChange={handleCustomerNameChange}
            value={currentCustomerName}
          />
          <Button onClick={handleCustomerNameSubmitted}>+</Button>
        </InputGroup>
      </div>
      <div
        id="similar-customers-display"
        className="container d-flex flex-row flex-wrap mt-3 p-0"
      >
        <div id="similar-to-text" className="p-2">
          Similar to:
        </div>
        {customerNames.map((customerName) => (
          <CustomerChip
            key={customerName}
            customerName={customerName}
            onClose={handleChipRemoval}
          />
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
