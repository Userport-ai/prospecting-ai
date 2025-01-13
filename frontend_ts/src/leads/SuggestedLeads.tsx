import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import LeadActivityParser from "./LeadActivityParser";

// TODO: Move this to services/ once available via API.
interface SuggestedLead {
  id: string;
  full_name: string;
  first_name: string;
  last_name: string;
  title: string;
  linkedin_url: string;
  email: string | null;
  about_description: string | null;
  current_role: {
    title: string;
    department: string;
    seniority: string;
    years_in_role: number | null;
    description: string | null;
  };
  location: string | null;
  skills: string[];
  education: {
    degree: string;
    institution: string;
    year: number | null;
  }[];
  // AI populated fields.
  fit_score: number;
  rationale: string;
  matching_criteria: string[];
  persona_match: string | null;
  recommended_approach: string;
}

interface RecommendationsViewProps {
  suggestedLeads: SuggestedLead[];
  selectedLeads: Set<string>;
  handleSelectLead: (lead: string) => void;
}

const RecommendationsTableView: React.FC<RecommendationsViewProps> = ({
  suggestedLeads,
  selectedLeads,
  handleSelectLead,
}) => {
  return (
    <div className="rounded-2xl border border-purple-300 p-2 shadow-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12"></TableHead>
            <TableHead className="text-purple-800">Score</TableHead>
            <TableHead className="text-purple-800">Name</TableHead>
            <TableHead className="text-purple-800">Title</TableHead>
            <TableHead className="text-purple-800">Persona</TableHead>
            <TableHead className="text-purple-800">LinkedIn</TableHead>
            <TableHead className="text-purple-800">About</TableHead>
            <TableHead className="text-purple-800">Years in Role</TableHead>
            <TableHead className="text-purple-800">Rationale</TableHead>
            <TableHead className="text-purple-800">Matching Criteria</TableHead>
            <TableHead className="text-purple-800">
              Recommended Approach
            </TableHead>
          </TableRow>
        </TableHeader>
        {/* Table Body */}
        <TableBody>
          {suggestedLeads.length > 0 ? (
            suggestedLeads.map((lead) => (
              <TableRow
                key={lead.id}
                className="hover:bg-gradient-to-r from-purple-100 to-purple-50 transition-all rounded-md"
              >
                <TableCell className="text-center">
                  <Checkbox
                    checked={selectedLeads.has(lead.id)}
                    onCheckedChange={() => handleSelectLead(lead.id)}
                  />
                </TableCell>
                <TableCell>{lead.fit_score}</TableCell>
                <TableCell>
                  {lead.first_name} {lead.last_name}
                </TableCell>
                <TableCell>{lead.title}</TableCell>
                <TableCell>{lead.persona_match}</TableCell>
                <TableCell>
                  <a
                    href={lead.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    View Profile
                  </a>
                </TableCell>
                <TableCell>{lead.about_description}</TableCell>
                <TableCell>{lead.current_role.years_in_role}</TableCell>
                <TableCell>{lead.rationale}</TableCell>
                <TableCell>{lead.matching_criteria}</TableCell>
                <TableCell>{lead.recommended_approach}</TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={5}
                className="text-center text-gray-500 rounded-b-lg"
              >
                No suggested leads available.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
};

interface SuggestedLeadsProps {
  suggestedLeads: SuggestedLead[];
  onAddLeads: () => void;
}

const SuggestedLeads: React.FC<SuggestedLeadsProps> = ({
  suggestedLeads,
  onAddLeads,
}) => {
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());

  // Handle if lead is selected or unselected.
  const handleSelectLead = (leadId: string) => {
    setSelectedLeads((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(leadId)) {
        newSet.delete(leadId);
      } else {
        newSet.add(leadId);
      }
      return newSet;
    });
  };

  // Add selected leads to the main list.
  const handleAddLeads = () => {
    // TODO: call backend.

    // Remove selected leads from the local list after successful call to the backend.

    // Call parent compoennt.
    onAddLeads();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div className="flex flex-col">
          <h2 className="text-lg font-semibold text-gray-600">
            AI Recommeded Leads
          </h2>
          <p className="text-gray-500">Based on analyzing the playbook</p>
        </div>

        {selectedLeads.size > 0 && (
          <Button onClick={handleAddLeads}>Add Selected Leads</Button>
        )}
      </div>

      <RecommendationsTableView
        suggestedLeads={suggestedLeads}
        selectedLeads={selectedLeads}
        handleSelectLead={handleSelectLead}
      />

      {/* Testing LinkedIn activity scraper flow, remove after done */}
      <LeadActivityParser linkedInUrl="https://www.linkedin.com/in/rohitmalik8/" />
    </div>
  );
};

export default SuggestedLeads;
