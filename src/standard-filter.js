import "./standard-filter.css";
import { Card, Form, CloseButton } from "react-bootstrap";
import {
  getCompanyHeadcountValues,
  getIndustryValues,
  getRegionValues,
  getFunctionNameValues,
  getFunctionHeadcountRangeValues,
} from "./standard-filters-data";

// Global constant describing None Key Id.
const noneKey = "none";

function OptionsList({ selectionValues, defaultValue = "" }) {
  return (
    <>
      <Form.Select>
        <option key={noneKey} value={noneKey}>
          {defaultValue}
        </option>
        {selectionValues.map((value) => (
          <option key={value.key} value={value.key}>
            {value.humanReadableString}
          </option>
        ))}
      </Form.Select>
    </>
  );
}

function FilterBody({ children }) {
  return (
    <div className="standard-filter-select container d-flex flex-column justify-content-start mt-1 p-0">
      {children}
    </div>
  );
}

function FunctionHeadCount() {
  return (
    <FilterBody>
      <OptionsList
        selectionValues={getFunctionNameValues()}
        defaultValue="Name"
      />
      <OptionsList
        selectionValues={getFunctionHeadcountRangeValues()}
        defaultValue="Headcount"
      />
    </FilterBody>
  );
}

function CompanyHeadCount() {
  return (
    <FilterBody>
      <OptionsList selectionValues={getCompanyHeadcountValues()} />
    </FilterBody>
  );
}

function Region() {
  return (
    <FilterBody>
      <OptionsList selectionValues={getRegionValues()} />
    </FilterBody>
  );
}

function Industry() {
  return (
    <FilterBody>
      <OptionsList selectionValues={getIndustryValues()} />
    </FilterBody>
  );
}

function StandardFilterInputs({ filterId }) {
  switch (filterId) {
    case "industry":
      return <Industry />;
    case "region":
      return <Region />;
    case "company-headcount":
      return <CompanyHeadCount />;
    case "function-headcount":
      return <FunctionHeadCount />;
    default:
      return null;
  }
}

function StandardFilter({ filterOption, onClose }) {
  function handleFilterClose(e) {
    e.stopPropagation();
    onClose(filterOption.id);
  }

  return (
    <div className="container d-flex flex-column">
      <Card className="mt-3">
        <Card.Body>
          <div className="container d-flex flex-row justify-content-between p-0">
            <div className="standard-filter-text">
              {filterOption.humanReadableString}
            </div>
            <CloseButton size="sm" onClick={handleFilterClose} />
          </div>
          <StandardFilterInputs filterId={filterOption.id} />
        </Card.Body>
      </Card>
    </div>
  );
}

export default StandardFilter;
