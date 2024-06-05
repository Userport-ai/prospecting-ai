import "./create-account-filters.css";
import { Accordion, Form } from "react-bootstrap";
import RelevanceFilter from "./relevance-filter";
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

function CreateAccountFilters() {
  const [relevanceFilterIdList, setRelevanceFilterIdList] = useState([]);

  function handleRelevanceFilterSelection(e) {
    e.stopPropagation();
    let newFilterId = e.target.value;
    if (
      newFilterId !== noneKey &&
      !relevanceFilterIdList.includes(newFilterId)
    ) {
      setRelevanceFilterIdList([...relevanceFilterIdList, newFilterId]);
    }
  }

  function handleRelevanceFilterRemoval(filterId) {
    setRelevanceFilterIdList(
      relevanceFilterIdList.filter((id) => id !== filterId)
    );
  }

  return (
    <div
      id="create-account-filters-outer-body"
      className="container d-flex flex-row justify-content-center"
    >
      <div id="create-account-filters" className="d-flex flex-column mt-5 pb-3">
        <div
          id="create-account-filters-filter"
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
              onChange={handleRelevanceFilterSelection}
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
          {relevanceFilterIdList.map((filterId) => {
            // Fetch filter option with current filter Id.
            let filterOption = relevanceFilters.find(
              (option) => option.id === filterId
            );

            return (
              <RelevanceFilter
                key={filterId}
                filterOption={filterOption}
                onClose={handleRelevanceFilterRemoval}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default CreateAccountFilters;
