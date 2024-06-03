import "./relevance-filter.css";
import { Form } from "react-bootstrap";

function RaisedFunding() {
  return (
    <div
      id="raised-funding-container"
      className="container d-flex flex-row justify-content-start mt-3"
    >
      <div class="p-1">
        <p>In the last </p>
      </div>
      <Form.Select className="ms-3">
        <option value="none" selected></option>
        <option value="3months">3 months</option>
        <option value="6months">6 months</option>
        <option value="12months">12 months</option>
      </Form.Select>
    </div>
  );
}

function RelevanceFilterInputs({ filterId }) {
  switch (filterId) {
    case "raised-funding-recently":
      return <RaisedFunding />;
    default:
      return null;
  }
}

export default RelevanceFilterInputs;
