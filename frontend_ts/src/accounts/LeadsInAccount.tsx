import LeadsTable from "@/leads/LeadsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SuggestedLeads from "@/leads/SuggestedLeads";
import { Lead } from "@/services/Leads";
import { useState } from "react";

enum LeadViewTab {
  LEADS = "leads",
  SUGGESTED_LEADS = "suggested_leads",
}

// TODO: Call server to fetch suggested leads.
const mockSuggestedLeads = [
  {
    id: "1",
    full_name: "Michael Brown",
    first_name: "Michael",
    last_name: "Brown",
    title: "CTO",
    linkedin_url: "https://linkedin.com/in/michaelbrown",
    email: "michael.brown@acme.com",
    about_description:
      "I lead a team of 200 to set tech roadmap for the company.",
    current_role: {
      title: "CTO",
      department: "Engineering",
      seniority: "Executive",
      years_in_role: 2,
      description:
        "Lead development of fintech products using cutting edge technologies",
    },
    location: "San Franciso, United States",
    skills: ["Backend, Algorithms"],
    education: [
      {
        degree: "Masters in Computer Science",
        institution: "Brown University",
        year: 1994,
      },
    ],
    fit_score: 0.8,
    rationale:
      "Heads the engineering team so will be the final stakeholder to convince to purchase your product",
    matching_criteria: [
      "Cares about efficiency based on LinkedIn profile, Has worked with similar tools in the past",
    ],
    persona_match: "Buyer",
    recommended_approach:
      "In your outreach, explain how your product will cut down time spent by his team and make them more productive",
  },
  {
    id: "2",
    full_name: "Sarah Johnson",
    first_name: "Sarah",
    last_name: "Johnson",
    title: "Director of Product",
    linkedin_url: "https://linkedin.com/in/sarahjohnson",
    email: "sarah.johnson@acme.com",
    about_description:
      "I have over 20 years experience in building and leading Product teams",
    current_role: {
      title: "Director of Product",
      department: "Product",
      seniority: "Executive",
      years_in_role: 0.3,
      description:
        "I lead a team of 8 Product Leaders to build roadmap and features for our product",
    },
    location: "New York, United States",
    skills: ["Product", "Design", "UI/UX"],
    education: [
      {
        degree: "MBA",
        institution: "Kellog",
        year: 2010,
      },
    ],
    fit_score: 0.45,
    persona_match: "Influencer",
    rationale:
      "They will be able to influence the buyer because they are on the executive team",
    matching_criteria: ["It helps their team ship products faster"],
    recommended_approach:
      "Highlight the ROI for their team provided by the product",
  },
];

// Display Leads in a table and also the suggested
// leads as recommended by AI.
const LeadsInAccount = () => {
  const [activeTab, setActiveTab] = useState<string>(LeadViewTab.LEADS);

  const tabTriggerClass =
    "w-full text-gray-700 hover:text-purple-700 py-2 px-4 transition-all duration-300 ease-in-out rounded-lg focus-visible:ring-2 focus-visible:ring-purple-500 data-[state=active]:bg-purple-100 data-[state=active]:text-purple-700 data-[state=active]:border-purple-500";

  // Handler once suggested leads are added by User.
  const onAddLeads = () => {
    // Switch tabs.
    setActiveTab(LeadViewTab.LEADS);
  };

  return (
    <div>
      <h1 className="font-bold text-gray-700 text-3xl mb-4 border-b-2 border-purple-400 w-fit">
        Dabur
      </h1>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-[30rem] h-fit p-2 mb-5 mt-2 shadow-md gap-4 bg-purple-50">
          <TabsTrigger value={LeadViewTab.LEADS} className={tabTriggerClass}>
            Leads
          </TabsTrigger>
          <TabsTrigger
            value={LeadViewTab.SUGGESTED_LEADS}
            className={tabTriggerClass}
          >
            AI Suggestions
          </TabsTrigger>
        </TabsList>
        <TabsContent value={LeadViewTab.LEADS}>
          <LeadsTable />
        </TabsContent>
        <TabsContent value={LeadViewTab.SUGGESTED_LEADS}>
          <SuggestedLeads
            suggestedLeads={mockSuggestedLeads}
            onAddLeads={onAddLeads}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeadsInAccount;
