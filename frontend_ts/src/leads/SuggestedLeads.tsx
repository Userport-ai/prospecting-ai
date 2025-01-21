import React, { useEffect, useState } from "react";
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
import { ParsedHTML } from "@/services/Extension";
import { cn } from "@/lib/utils";
import ScreenLoader from "@/common/ScreenLoader";
import {
  approveLead,
  enrichLinkedInActivity,
  Lead,
  listSuggestedLeads,
} from "@/services/Leads";
import { useAuthContext } from "@/auth/AuthProvider";

interface ParsedLead {
  id: string;
  parsedHTML?: ParsedHTML;
  errorMessage?: String;
}

interface RecommendationsViewProps {
  suggestedLeads: Lead[];
  selectedLeads: Set<string>;
  handleSelectLead: (lead: string) => void;
  handleAddLeads: () => void;
  startParsing: boolean;
  onParsingSuccess: (lead_id: string, parsedHTML: ParsedHTML) => void;
  onParsingError: (lead_id: string, errorMessage: string) => void;
}

const RecommendationsTableView: React.FC<RecommendationsViewProps> = ({
  suggestedLeads,
  selectedLeads,
  handleSelectLead,
  handleAddLeads,
  startParsing,
  onParsingSuccess,
  onParsingError,
}) => {
  return (
    <div className={cn("flex flex-col gap-4", startParsing ? "hidden" : "")}>
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
              <TableHead className="text-purple-800">
                Matching Criteria
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
                  <TableCell>
                    {lead.custom_fields
                      ? lead.custom_fields.evaluation.fit_score
                      : null}
                  </TableCell>
                  <TableCell>
                    {lead.first_name} {lead.last_name}
                  </TableCell>
                  <TableCell>{lead.role_title}</TableCell>
                  <TableCell>
                    {lead.custom_fields
                      ? lead.custom_fields.evaluation.persona_match
                      : null}
                  </TableCell>
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
                  <TableCell>{lead.enrichment_data?.summary ?? ""}</TableCell>
                  <TableCell>
                    {lead.enrichment_data?.total_years_experience ?? "Unknown"}
                  </TableCell>
                  <TableCell>
                    {lead.custom_fields
                      ? lead.custom_fields.evaluation.rationale
                      : null}
                  </TableCell>
                  <TableCell>
                    {lead.custom_fields
                      ? lead.custom_fields.evaluation.matching_criteria.join(
                          ", "
                        )
                      : null}
                  </TableCell>
                  {selectedLeads.has(lead.id) && (
                    <LeadActivityParser
                      leadId={lead.id}
                      linkedInUrl={lead.linkedin_url}
                      startParsing={startParsing}
                      onComplete={onParsingSuccess}
                      onError={onParsingError}
                    />
                  )}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={14}
                  className="text-center text-gray-500 rounded-b-lg"
                >
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

// View to display activity parsing in progress state.
const ActivityParsingInProgress = () => {
  return (
    <div className="flex justify-center items-center min-h-80 border">
      <div className="flex flex-col gap-6 w-5/12">
        <div className="flex flex-col gap-2">
          <p>LinkedIn Activity Parsing is in Progress for selected leads.</p>
          <p className="text-destructive">
            Do not close this Tab or progress will be lost!
          </p>
          <p className="text-destructive">
            Do not open or close the LinkedIn tabs created.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <ScreenLoader />
        </div>
      </div>
    </div>
  );
};

const DisplayParsingErrors: React.FC<{ parsedLeads: ParsedLead[] }> = ({
  parsedLeads,
}) => {
  const leadsWithError = parsedLeads.filter(
    (lead) => lead.errorMessage !== undefined
  );
  if (leadsWithError.length === 0) {
    return null;
  }
  return (
    <div className="w-fit py-2 px-4 flex flex-col border border-red-500">
      <p className=" mb-2 text-destructive font-semibold">
        Errors from Activity Parsing
      </p>
      {leadsWithError.map((lead, idx) => (
        <p key={lead.id} className="text-gray-500 font-medium">
          {idx + 1}. {lead.errorMessage}
        </p>
      ))}
    </div>
  );
};

interface SuggestedLeadsProps {
  accountId: string;
  onAddLeads: () => void;
}

const SuggestedLeads: React.FC<SuggestedLeadsProps> = ({
  accountId,
  onAddLeads,
}) => {
  const authContext = useAuthContext();
  const [suggestedLeads, setSuggestedLeads] = useState<Lead[]>([]);
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());
  const [startParsing, setStartParsing] = useState<boolean>(false);
  const [parsedLeads, setParsedLeads] = useState<ParsedLead[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listSuggestedLeads(authContext, accountId)
      .then((leads) =>
        setSuggestedLeads(
          leads.sort((l1, l2) => (l2.score ?? 0) - (l1.score ?? 0))
        )
      )
      .catch((error) =>
        setErrorMessage(`Failed to fetch Suggested leads: ${String(error)}`)
      )
      .finally(() => setLoading(false));
  }, []);

  // Handle if lead is selected or unselected and updated selected leads list.
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
    setStartParsing(true);
  };

  // Handle Parsing complete for given Lead ID.
  const onParsingSuccess = (leadId: string, parsedHTML: ParsedHTML) => {
    setParsedLeads((parsedLeads) => [
      ...parsedLeads,
      { id: leadId, parsedHTML: parsedHTML },
    ]);
  };

  // Handle Parsing error for given Lead ID.
  const onParsingError = (leadId: string, errorMessage: string) => {
    setParsedLeads((parsedLeads) => [
      ...parsedLeads,
      {
        id: leadId,
        complete: true,
        errorMessage: `Lead: ${leadId}, Error: ${errorMessage}`,
      },
    ]);
  };

  useEffect(() => {
    if (!startParsing) {
      return;
    }
    const allLeadsParsed =
      selectedLeads.size === parsedLeads.length &&
      parsedLeads.every((lead) => selectedLeads.has(lead.id));
    if (!allLeadsParsed) {
      // Not all leads are parsed, do nothing.
      return;
    }

    // Parsing complete.
    setStartParsing(false);

    setLoading(true);
    const promises = parsedLeads
      .filter((lead) => lead.parsedHTML !== undefined)
      .map((parsedLead) => {
        approveLead(authContext, parsedLead.id)
          .then((_) =>
            enrichLinkedInActivity(
              authContext,
              parsedLead.id,
              parsedLead.parsedHTML!
            )
          )
          .catch((error) => Promise.reject(error));
      });

    Promise.all(promises)
      .then(() => {
        // All leads processed
        setLoading(false);
        onAddLeads();
      })
      .catch((error) => {
        // Handle the overall error (e.g., if any of the promises rejected)
        setErrorMessage(
          `Failed to Approve some or all the leads: ${String(error)}`
        );
        setLoading(false);
      });
  }, [startParsing, parsedLeads]);

  if (loading) {
    return <ScreenLoader />;
  }

  return (
    <div className="flex flex-col gap-2">
      {errorMessage && <p className="text-destructive">{errorMessage}</p>}
      <DisplayParsingErrors parsedLeads={parsedLeads} />
      {startParsing && <ActivityParsingInProgress />}
      <RecommendationsTableView
        suggestedLeads={suggestedLeads}
        selectedLeads={selectedLeads}
        handleSelectLead={handleSelectLead}
        handleAddLeads={handleAddLeads}
        startParsing={startParsing}
        onParsingSuccess={onParsingSuccess}
        onParsingError={onParsingError}
      />
    </div>
  );
};

export default SuggestedLeads;
