import LeadsTable from "@/leads/LeadsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SuggestedLeads from "@/leads/SuggestedLeads";
import { Lead } from "@/services/Leads";
import { EnrichmentStatus } from "@/services/Common";
import { Sparkles } from "lucide-react";

enum LeadViewTab {
  LEADS = "leads",
  SUGGESTED_LEADS = "suggested_leads",
}

const mockSuggestedLeads = [
  {
    id: "1",
    first_name: "Michael",
    last_name: "Brown",
    role_title: "CTO",
    linkedin_url: "https://linkedin.com/in/michaelbrown",
    email: "michael.brown@acme.com",
    phone: "+1-555-0456",
    score: 0.7,
    account_details: {
      id: "a05bae8e-6f80-4e18-99ab-1ed69eefcd92",
      name: "Tech Innovators Inc",
      industry: "AI & Machine Learning",
    },
    enrichment_status: EnrichmentStatus.COMPLETED,
    created_at: "2024-05-01",
    custom_fields: null,
    last_enriched_at: null,
  },
  {
    id: "2",
    first_name: "Sarah",
    last_name: "Johnson",
    role_title: "Director of Product",
    linkedin_url: "https://linkedin.com/in/sarahjohnson",
    email: "sarah.johnson@acme.com",
    phone: null,
    score: 0.45,
    account_details: {
      id: "a05bae8e-6f80-4e18-99ab-1ed69eefcd92",
      name: "Tech Innovators Inc",
      industry: "AI & Machine Learning",
    },
    enrichment_status: EnrichmentStatus.COMPLETED,
    created_at: "2024-05-01",
    custom_fields: null,
    last_enriched_at: null,
  },
];

// Display Leads in a table and also the suggested
// leads as recommended by AI.
const LeadsInAccount = () => {
  const tabTriggerClass =
    "w-full text-gray-700 hover:text-purple-700 py-2 px-4 transition-all duration-300 ease-in-out rounded-lg focus-visible:ring-2 focus-visible:ring-purple-500 data-[state=active]:bg-purple-100 data-[state=active]:text-purple-700 data-[state=active]:border-purple-500";

  const onAddLeads = (leads: Lead[]) => {
    console.log("added leads: ,", leads);
  };
  return (
    <div>
      <h1 className="font-bold text-gray-700 text-3xl mb-4 border-b-2 border-purple-400 w-fit">
        Dabur
      </h1>
      <Tabs defaultValue={LeadViewTab.LEADS}>
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
