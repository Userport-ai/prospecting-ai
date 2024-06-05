export const standardFilters = [
  {
    id: "industry",
    humanReadableString: "Industry",
    selections: [
      {
        humanReadableString: "Industry",
        values: [
          {
            key: "sass",
            humanReadableString: "SaaS",
          },
          {
            key: "real-estate",
            humanReadableString: "Real Estate",
          },
          {
            key: "banking",
            humanReadableString: "Banking",
          },
          {
            key: "media-entertainment",
            humanReadableString: "Media & Entertainment",
          },
        ],
      },
    ],
  },
  {
    id: "region",
    humanReadableString: "Region",
    selections: [
      {
        humanReadableString: "Region",
        values: [
          {
            key: "amer",
            humanReadableString: "AMER",
          },
          {
            key: "emea",
            humanReadableString: "EMEA",
          },
          {
            key: "apac",
            humanReadableString: "APAC",
          },
        ],
      },
    ],
  },
  {
    id: "company-headcount",
    humanReadableString: "Company Headcount",
    selections: [
      {
        humanReadableString: "Company Headcount",
        values: [
          {
            key: "1-10",
            humanReadableString: "1-10",
          },
          {
            key: "10-50",
            humanReadableString: "10-50",
          },
          {
            key: "50-100",
            humanReadableString: "50-100",
          },
          {
            key: "100-300",
            humanReadableString: "100-300",
          },
          {
            key: "300-500",
            humanReadableString: "300-500",
          },
          {
            key: "500-1000",
            humanReadableString: "500-1000",
          },
          {
            key: "1000-5000",
            humanReadableString: "1000-5000",
          },
          {
            key: "5000+",
            humanReadableString: "greater than 5000",
          },
        ],
      },
    ],
  },
  {
    id: "function-headcount",
    humanReadableString: "Function Headcount",
    selections: [
      {
        humanReadableString: "Name",
        values: [
          {
            key: "marketing",
            humanReadableString: "Marketing",
          },
          {
            key: "sales",
            humanReadableString: "Sales",
          },
          {
            key: "engineering",
            humanReadableString: "Engineering",
          },
        ],
      },
      {
        humanReadableString: "Headcount",
        values: [
          {
            key: "1-10",
            humanReadableString: "Less than 10",
          },
          {
            key: "10-20",
            humanReadableString: "Between 10 to 20",
          },
          {
            key: "20-30",
            humanReadableString: "Between 20 to 30",
          },
        ],
      },
    ],
  },
];

export function getIndustryValues() {
  return getFilterValues("industry", "Industry");
}

export function getRegionValues() {
  return getFilterValues("region", "Region");
}

export function getCompanyHeadcountValues() {
  return getFilterValues("company-headcount", "Company Headcount");
}

export function getFunctionNameValues() {
  return getFilterValues("function-headcount", "Name");
}

export function getFunctionHeadcountRangeValues() {
  return getFilterValues("function-headcount", "Headcount");
}

// Returns filter values for given filter ID and specific filter name.
function getFilterValues(id, name) {
  const gotFilterWithId = standardFilters.find((f) => f.id === id);
  return gotFilterWithId.selections.find((x) => x.humanReadableString === name)
    .values;
}
