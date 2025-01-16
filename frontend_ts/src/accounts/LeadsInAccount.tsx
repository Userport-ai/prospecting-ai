import LeadsTable from "@/leads/LeadsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SuggestedLeads from "@/leads/SuggestedLeads";
import { useState } from "react";

enum LeadViewTab {
  LEADS = "leads",
  SUGGESTED_LEADS = "suggested_leads",
}

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
          <SuggestedLeads onAddLeads={onAddLeads} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeadsInAccount;
