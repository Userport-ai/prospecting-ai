import "./relevance-filter.css";
import { Form } from "react-bootstrap";

function RaisedFunding() {
  return (
    <div
      id="raised-funding-container"
      className="container d-flex flex-row justify-content-start mt-3 p-0"
    >
      <div class="p-0">
        <p>In the last </p>
      </div>
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

function RelevanceFilterInputs({ filterId }) {
  switch (filterId) {
    case "raised-funding-recently":
      return <RaisedFunding />;
    case "hiring-recently":
      return <IsHiring />;
    default:
      return null;
  }
}

export default RelevanceFilterInputs;
