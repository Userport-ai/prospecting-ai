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

interface SuggestedLeadsProps {
  suggestedLeads: Lead[]; // List of suggested leads
  onAddLeads: (leads: Lead[]) => void; // Callback to add selected leads to the final Leads Table
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
    setSelectedLeads(new Set()); // Clear selection after adding leads
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-600">
          Recommended Leads
        </h2>
        <Button
          onClick={handleAddLeads}
          disabled={selectedLeads.size === 0}
          className="disabled:bg-gray-600 text-white hover:bg-purple-600"
        >
          Add to Leads List
        </Button>
      </div>

      <div className="rounded-md border border-gray-300 bg-white shadow-sm">
        <Table>
          {/* Table Header */}
          <TableHeader>
            <TableRow>
              <TableHead className="w-12"></TableHead>
              <TableHead>Name</TableHead>
              <TableHead>LinkedIn</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Score</TableHead>
            </TableRow>
          </TableHeader>

          {/* Table Body */}
          <TableBody>
            {suggestedLeads.length > 0 ? (
              suggestedLeads.map((lead) => (
                <TableRow key={lead.id}>
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
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-gray-500">
                  No suggested leads available.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default SuggestedLeads;
