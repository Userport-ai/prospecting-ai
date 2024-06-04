import "./create-icp.css";
import { Accordion, Button, Form, CloseButton, Card } from "react-bootstrap";
import RelevanceFilterInputs from "./relevance-filter";
import { useState } from "react";
import {
  industrySelection,
  regionSelection,
  companyHeadcountSelection,
  functionNameSelection,
} from "./standard-filters-data";

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

function FormSelection({ options, defaultHumanReadableValue = "", className }) {
  return (
    <Form.Select size="sm" className={className}>
      <option value="none">{defaultHumanReadableValue}</option>
      {options.map((option) => (
        <option value={option.key}>{option.humanReadableString}</option>
      ))}
    </Form.Select>
  );
}

function AccordianSelection({ name, className, children }) {
  return (
    <div className={"container d-flex flex-column " + className}>
      <Accordion alwaysOpen>
        <Accordion.Item eventKey={name}>
          <Accordion.Header>{name}</Accordion.Header>
          <Accordion.Body>{children}</Accordion.Body>
        </Accordion.Item>
      </Accordion>
    </div>
  );
}

function CreateICP() {
  return (
    <div
      id="create-icp-outer-body"
      className="container d-flex flex-row justify-content-center"
    >
      <div id="create-icp" className="d-flex flex-column mt-5 pb-3">
        <div
          id="create-icp-filter"
          className="container  d-flex flex-column align-items-center"
        >
          <div
            id="account-profile-title"
            className="container d-flex justify-content-center mt-2 mb-2"
          >
            <p>Account Profile</p>
          </div>
          <div className="filters-title container mt-2">
            <p>Standard Filters</p>
          </div>
          <AccordianSelection name={industrySelection.name}>
            <FormSelection options={industrySelection.options}></FormSelection>
          </AccordianSelection>
          <AccordianSelection name={regionSelection.name} className="mt-4">
            <FormSelection options={regionSelection.options}></FormSelection>
          </AccordianSelection>
          <AccordianSelection
            name={companyHeadcountSelection.name}
            className="mt-4"
          >
            <FormSelection
              options={companyHeadcountSelection.options}
            ></FormSelection>
          </AccordianSelection>
          <AccordianSelection
            name={functionNameSelection.name}
            className="mt-4"
          >
            <FormSelection
              options={functionNameSelection.nameOptions}
              defaultHumanReadableValue="Name"
            ></FormSelection>
            <FormSelection
              options={functionNameSelection.headcountOptions}
              defaultHumanReadableValue="Headcount"
              className="mt-2"
            ></FormSelection>
          </AccordianSelection>

          <div
            id="relevance-filter-id"
            className="filters-title container d-flex mt-5"
          >
            <div className="d-flex flex-column justify-content-center">
              Relevance Filters
            </div>
            <Button>+</Button>
          </div>
          <div className="container d-flex flex-column">
            <RelevanceFilter />
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateICP;
