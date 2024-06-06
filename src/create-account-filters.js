import "./create-account-filters.css";
import { Form } from "react-bootstrap";
import StandardFilter from "./standard-filter";
import RelevanceFilter from "./relevance-filter";
import { relevanceFilters } from "./relevance-filters-data";
import { standardFilters } from "./standard-filters-data";
import { useState } from "react";

// Global constant describing None Key Id.
const noneKey = "none";

function StandardAccountFilters() {
  const [standardFilterIdList, setStandardFilterIdList] = useState([]);

  function handleStandardFilterSelection(e) {
    // Do nothing for now.
    e.stopPropagation();
    let newFilterId = e.target.value;
    if (
      newFilterId !== noneKey &&
      !standardFilterIdList.includes(newFilterId)
    ) {
      setStandardFilterIdList([...standardFilterIdList, newFilterId]);
    }
  }

  function handleStandardFilterRemoval(filterId) {
    setStandardFilterIdList(
      standardFilterIdList.filter((id) => id !== filterId)
    );
  }

  return (
    <>
      <div className="filters-title container mt-2">
        <p>Standard Filters</p>
      </div>
      <div className="container mt-2">
        <Form.Select
          size="sm"
          onChange={handleStandardFilterSelection}
          value={noneKey}
        >
          <option key={noneKey} value={noneKey}>
            {" "}
            Add a filter{" "}
          </option>
          {standardFilters.map((filter) => (
            <option key={filter.id} value={filter.id}>
              {filter.humanReadableString}
            </option>
          ))}
        </Form.Select>
      </div>

      {standardFilterIdList.map((filterId) => {
        // Fetch filter option with current filter Id.
        let filterOption = standardFilters.find(
          (option) => option.id === filterId
        );

        return (
          <StandardFilter
            key={filterId}
            filterOption={filterOption}
            onClose={handleStandardFilterRemoval}
          />
        );
      })}
    </>
  );
}

function RelevanceAccountFilters() {
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
    <>
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
    </>
  );
}

function CreateAccountFilters() {
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
            <p>Select Account Filters</p>
          </div>
          <StandardAccountFilters />
          <RelevanceAccountFilters />
        </div>
      </div>
    </div>
  );
}

export default CreateAccountFilters;
