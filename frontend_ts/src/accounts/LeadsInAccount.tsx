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
  {
    id: "3",
    full_name: "Rohit Malik",
    first_name: "Rohit",
    last_name: "Malik",
    title: "Director - Global Sales and Revenue Operations",
    linkedin_url: "https://www.linkedin.com/in/rohitmalik8/",
    email: "rohit.malik@acme.com",
    about_description:
      "Experienced Senior Sales Ops Professional driving revenue growth, operational efficiency and optimizing sales processes. I specialize in designing and implementing strategic sales operations initiatives that enhance efficiency, streamline workflows, and maximize sales team performance." +
      "I am a results-oriented sales operations leader with a proven track record of success in optimizing sales processes, enhancing productivity, and increasing revenue. With a strong analytical mindset and a keen eye for identifying opportunities, I excel at leveraging data-driven insights to guide strategic decision-making and align sales operations with overall business objectives." +
      "" +
      "Throughout my career, I have successfully led cross-functional teams and collaborated with key stakeholders to develop and execute data-driven strategies that improve sales forecasting, territory planning, and pipeline management. I possess a deep understanding of CRM systems and sales automation tools, leveraging technology to enhance sales operations effectiveness. I have a deep understanding of sales processes, forecasting methodologies, and pipeline management, enabling me to drive sales performance and deliver measurable results." +
      "Collaboration is at the heart of my approach. I thrive in cross-functional environments, forging strong partnerships with sales teams, marketing, finance, and other stakeholders to ensure alignment and drive cohesive sales operations. I am skilled in implementing sales enablement programs, providing training and support to empower sales teams, and fostering a culture of continuous improvement." +
      "As a Senior Sales Ops Professional, I am dedicated to optimizing sales processes, enhancing sales effectiveness, and driving revenue growth. I am passionate about leveraging technology and automation to streamline operations, improve scalability, and enhance the overall customer experience." +
      "" +
      "I am passionate about leveraging my expertise to help organizations achieve their sales objectives, optimize operations, and fuel sustainable growth. If you are looking for a seasoned Sales Ops professional who can drive transformative change and deliver results, let's connect and explore how we can collaborate for mutual success. Together, we can achieve remarkable sales performance and surpass business objectives.",
    current_role: {
      title: "Director - Global Sales and Revenue Operations",
      department: "Sales",
      seniority: "Executive",
      years_in_role: 3.25,
      description:
        "At CoreStack Inc., I lead Sales & Revenue Operations, focusing on strategy, analysis, and execution. I've been instrumental in annual revenue increase. Implemented sales incentive program, improved forecasting and reduced outstanding collectables. Key initiatives include digitalizing reporting capabilities, improving data-driven decision-making, and fostering cross-functional team collaboration.",
    },
    location: "Gurugram, Haryana, India",
    skills: ["Sales", "Revops", "Enterprise sales"],
    education: [
      {
        degree: "MBA",
        institution: "FORE School of Management",
        year: 2010,
      },
    ],
    fit_score: 0.45,
    persona_match: "buyer",
    rationale:
      "They will be able to influence the buyer because they are on the executive team",
    matching_criteria: ["It helps their team hit their revenue goals faster"],
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
