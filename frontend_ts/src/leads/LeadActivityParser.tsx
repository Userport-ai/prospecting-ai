import {
  getLinkedInActivityParsingResult,
  LinkedInActivityParsingResult,
  ParsedHTML,
  startLinkedInActivityParsing,
} from "@/services/Extension";
import { useEffect, useState } from "react";

interface LeadActivityParserProps {
  leadId: string;
  linkedInUrl: string;
  startParsing: boolean;
  onComplete: (leadId: string, parsedHTML: ParsedHTML) => void;
  onError: (leadId: string, errorMessage: string) => void;
}

// Parses LinkedIn Activity for the given Lead.
const LeadActivityParser: React.FC<LeadActivityParserProps> = ({
  leadId,
  linkedInUrl,
  startParsing,
  onComplete,
  onError,
}) => {
  const initialStatus = startParsing
    ? LinkedInActivityParsingResult.SCHEDULED
    : null;
  const [status, setStatus] = useState<LinkedInActivityParsingResult | null>(
    initialStatus
  );
  const [tabId, setTabId] = useState<number | null>(null); // LinkedIn Activity Tab Id.
  const POLLING_INTERVAL = 10 * 1000; // Poll every 10s.

  // Update status whenever startParsing value changes.
  useEffect(() => {
    if (startParsing) {
      // setStatus(LinkedInActivityParsingResult.SCHEDULED);
      // Wait for 0-3 seconds before starting so each activity starts at a different time.
      const startDelay = Math.floor(Math.random() * 3000);
      const intervalId = setTimeout(
        () => setStatus(LinkedInActivityParsingResult.SCHEDULED),
        startDelay
      );
      return () => clearTimeout(intervalId);
    } else {
      setStatus(null);
    }
  }, [startParsing]);

  useEffect(() => {
    switch (status) {
      case LinkedInActivityParsingResult.SCHEDULED:
        console.log("Starting Parsing for URL: ", linkedInUrl);
        startLinkedInActivityParsing(linkedInUrl)
          .then((response) => {
            setStatus(response.status);
            setTabId(response.tab_id);
          })
          .catch((error) => {
            setStatus(null);

            // Call parent with error.
            onError(leadId, String(error));
          });
        break;
      case LinkedInActivityParsingResult.IN_PROGRESS:
        if (!tabId) {
          // Call parent with error.
          onError(
            leadId,
            `Tab Id missing for URL: ${linkedInUrl}, cannot check parsing status`
          );
          return;
        }
        const intervalId = setInterval(async () => {
          getLinkedInActivityParsingResult(tabId, linkedInUrl)
            .then((response) => {
              if (response.status === LinkedInActivityParsingResult.COMPLETE) {
                // Parsing is complete.
                setTabId(null);

                // Call parent with success.
                onComplete(leadId, response.parsed_data);
              }
              setStatus(response.status);
            })
            .catch((error) => {
              setStatus(null);

              // Call parent withe error.
              onError(leadId, String(error));
            });
        }, POLLING_INTERVAL);
        return () => clearInterval(intervalId);
      default:
      // Do nothing.
    }
  }, [status]);

  return null;
};

export default LeadActivityParser;
