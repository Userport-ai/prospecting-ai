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
import { Lead } from "@/services/Leads";

interface RecommendationsViewProps {
  suggestedLeads: Lead[];
  selectedLeads: Set<string>;
  handleSelectLead: (lead: string) => void;
}

const RecommendationsTableView: React.FC<RecommendationsViewProps> = ({
  suggestedLeads,
  selectedLeads,
  handleSelectLead,
}) => {
  return (
    <div className="min-w-fit rounded-2xl border border-purple-300 p-2 shadow-lg">
      <Table>
        {/* Table Header */}
        <TableHeader>
          <TableRow>
            <TableHead className="w-12"></TableHead>
            <TableHead className="text-purple-800">Name</TableHead>
            <TableHead className="text-purple-800">LinkedIn</TableHead>
            <TableHead className="text-purple-800">Role</TableHead>
            <TableHead className="text-purple-800">Score</TableHead>
            <TableHead className="text-purple-800">Rationale</TableHead>
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
                <TableCell>
                  {lead.first_name} {lead.last_name}
                </TableCell>
                <TableCell>
                  {lead.linkedin_url ? (
                    <a
                      href={lead.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      View Profile
                    </a>
                  ) : (
                    "N/A"
                  )}
                </TableCell>
                <TableCell>{lead.role_title || "N/A"}</TableCell>
                <TableCell>{lead.score || "N/A"}</TableCell>
                <TableCell>They fit the ICP well</TableCell>
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

const RecommendationsCardView: React.FC<RecommendationsViewProps> = ({
  suggestedLeads,
  selectedLeads,
  handleSelectLead,
}) => {
  return (
    <div className="grid grid-cols-1 gap-4">
      {suggestedLeads.length > 0 ? (
        suggestedLeads.map((lead) => (
          <div
            key={lead.id}
            className={`border ${
              selectedLeads.has(lead.id)
                ? "border-purple-600 bg-purple-50"
                : "border-purple-300 bg-white"
            } p-4 rounded-2xl shadow-md hover:shadow-lg transition-shadow`}
          >
            {/* Checkbox */}
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium text-purple-800">
                {lead.first_name} {lead.last_name}
              </h3>
              <Checkbox
                checked={selectedLeads.has(lead.id)}
                onCheckedChange={() => handleSelectLead(lead.id)}
                className="border border-purple-300"
              />
            </div>

            {/* LinkedIn URL */}
            {lead.linkedin_url && (
              <p className="text-sm text-blue-600 hover:underline">
                <a
                  href={lead.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  LinkedIn Profile
                </a>
              </p>
            )}

            {/* Role Title */}
            <p className="text-sm text-gray-600">
              <strong>Role:</strong> {lead.role_title || "N/A"}
            </p>

            {/* Score */}
            <p className="text-sm text-gray-600">
              <strong>Score:</strong> {lead.score || "N/A"}
            </p>

            {/* Industry */}
            {lead.account_details?.industry && (
              <p className="text-sm text-gray-600">
                <strong>Industry:</strong> {lead.account_details.industry}
              </p>
            )}
          </div>
        ))
      ) : (
        <p className="text-gray-500 col-span-full text-center">
          No suggested leads available.
        </p>
      )}
    </div>
  );
};

interface SuggestedLeadsProps {
  suggestedLeads: Lead[];
  onAddLeads: (leads: Lead[]) => void;
}

const SuggestedLeads: React.FC<SuggestedLeadsProps> = ({
  suggestedLeads,
  onAddLeads,
}) => {
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());

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

  const handleAddLeads = () => {
    const leadsToAdd = suggestedLeads.filter((lead) =>
      selectedLeads.has(lead.id)
    );
    onAddLeads(leadsToAdd);
    setSelectedLeads(new Set());
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

      {/* <RecommendationsTableView
        suggestedLeads={suggestedLeads}
        selectedLeads={selectedLeads}
        handleSelectLead={handleSelectLead}
      /> */}

      <RecommendationsCardView
        suggestedLeads={suggestedLeads}
        selectedLeads={selectedLeads}
        handleSelectLead={handleSelectLead}
      />
    </div>
  );
};

export default SuggestedLeads;
