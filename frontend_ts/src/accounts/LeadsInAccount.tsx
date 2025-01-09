import LeadsTable from "@/leads/LeadsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SuggestedLeads from "@/leads/SuggestedLeads";

enum LeadViewTab {
  LEADS = "leads",
  SUGGESTED_LEADS = "suggested_leads",
}

// Display Leads in a table and also the suggested
// leads as recommended by AI.
const LeadsInAccount = () => {
  return (
    <div>
      <Tabs defaultValue={LeadViewTab.LEADS}>
        <TabsList>
          <TabsTrigger value={LeadViewTab.LEADS}>Leads</TabsTrigger>
          <TabsTrigger value={LeadViewTab.SUGGESTED_LEADS}>
            Suggested by AI
          </TabsTrigger>
        </TabsList>
        <TabsContent value={LeadViewTab.LEADS}>
          <LeadsTable />
        </TabsContent>
        <TabsContent value={LeadViewTab.SUGGESTED_LEADS}>
          <SuggestedLeads />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeadsInAccount;
