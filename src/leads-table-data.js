export const emptyLeadsResult = {
  status: "success",
  leads: [],
};

// Mock data from server.
export const leadsResult = {
  status: "success",
  leads: [
    {
      id: "66ab9633a3bb9048bc1a0be5",
      creation_date: null,
      last_updated_date: null,
      person_linkedin_url: "https://www.linkedin.com/in/zperret",
      person_profile_id: null,
      company_profile_id: null,
      person_name: "Zachary Perret",
      company_name: "Plaid",
      person_role_title: "Co-Founder / CEO",
      status: "complete",
      company_headcount: 1222,
      company_industry_categories: [
        "banking",
        "finance",
        "financial-services",
        "fintech-e067",
        "insurtech",
        "software",
        "wealth-management",
      ],
      search_results_map: null,
      report_creation_date_readable_str: null,
      report_publish_cutoff_date: null,
      report_publish_cutoff_date_readable_str: null,
      details: null,
    },
  ],
};

// Mock data from server.
export const leadsInProgressResult = {
  status: "success",
  leads: [
    {
      id: "66ab9633a3bb9048bc1a0be5",
      creation_date: null,
      last_updated_date: null,
      person_linkedin_url: "https://www.linkedin.com/in/zperret",
      person_profile_id: null,
      company_profile_id: null,
      person_name: "Zachary Perret",
      company_name: "Plaid",
      person_role_title: "Co-Founder / CEO",
      status: "processed_contents_in_urls",
      company_headcount: 1222,
      company_industry_categories: [
        "banking",
        "finance",
        "financial-services",
        "fintech-e067",
        "insurtech",
        "software",
        "wealth-management",
      ],
      search_results_map: null,
      report_creation_date_readable_str: null,
      report_publish_cutoff_date: null,
      report_publish_cutoff_date_readable_str: null,
      details: null,
    },
  ],
};
