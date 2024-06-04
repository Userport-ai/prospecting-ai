import "./create-icp.css";
import { Accordion, Form, CloseButton, Card } from "react-bootstrap";
import RelevanceFilterInputs from "./relevance-filter";
import {
  industrySelection,
  regionSelection,
  companyHeadcountSelection,
  functionNameSelection,
} from "./standard-filters-data";
import { relevanceFilters } from "./relevance-filters-data";
import { useState } from "react";

// Global constant describing None Key Id.
const noneKey = "none";

function RelevanceFilter({ filterOption, onClose }) {
  function handleFilterClose(e) {
    e.stopPropagation();
    onClose(filterOption.id);
  }

  return (
    <div className="container d-flex flex-column">
      <Card className="mt-3">
        <Card.Body>
          <div
            id="relevance-filter-container"
            className="container d-flex flex-row justify-content-between"
          >
            <div className="relevance-filter-text">
              {filterOption.humanReadableString}
            </div>
            <CloseButton size="sm" onClick={handleFilterClose} />
          </div>
          <RelevanceFilterInputs filterId={filterOption.id} />
        </Card.Body>
      </Card>
    </div>
  );
}

function FormSelection({ options, defaultHumanReadableValue = "", className }) {
  return (
    <Form.Select size="sm" className={className}>
      <option key={noneKey} value={noneKey}>
        {defaultHumanReadableValue}
      </option>
      {options.map((option) => (
        <option key={option.key} value={option.key}>
          {option.humanReadableString}
        </option>
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
  const [filterIdList, setFilterIdList] = useState([]);

  function handleFilterSelection(e) {
    e.stopPropagation();
    let newFilterId = e.target.value;
    if (newFilterId !== noneKey && !filterIdList.includes(newFilterId)) {
      setFilterIdList([...filterIdList, newFilterId]);
    }
  }

  function handleFilterRemoval(filterId) {
    setFilterIdList(filterIdList.filter((id) => id !== filterId));
  }

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

          <div className="filters-title container d-flex mt-5">
            Relevance Filters
          </div>
          <div id="relevance-filter-selector" className="container mt-3">
            <Form.Select
              size="sm"
              onChange={handleFilterSelection}
              value={noneKey}
            >
              <option key={noneKey} value={noneKey}>
                {" "}
                Add a filter{" "}
              </option>
              {relevanceFilters.map((filter) => (
                <option key={filter.id} value={filter.id}>
                  {filter.humanReadableString}
                </option>
              ))}
            </Form.Select>
          </div>
          {filterIdList.map((filterId) => {
            // Fetch filter option with current filter Id.
            let filterOption = relevanceFilters.find(
              (option) => option.id === filterId
            );

            return (
              <RelevanceFilter
                key={filterId}
                filterOption={filterOption}
                onClose={handleFilterRemoval}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default CreateICP;
