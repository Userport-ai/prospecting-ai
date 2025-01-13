import { Button } from "@/components/ui/button";
import {
  getLinkedInActivityParsingResult,
  LinkedInActivityParsingResult,
  startLinkedInActivityParsing,
} from "@/services/Extension";
import { useEffect, useState } from "react";

// Parses LinkedIn Activity for given Lead's LinkedIn URL.
const LeadActivityParser: React.FC<{ linkedInUrl: string }> = ({
  linkedInUrl,
}) => {
  const [status, setStatus] = useState<LinkedInActivityParsingResult | null>(
    null
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tabId, setTabId] = useState<number | null>(null); // LinkedIn Activity Tab Id.
  const [parsedHTML, setParsedHTML] = useState<{
    posts_html?: string | null;
    comments_html?: string | null;
    reactions_html?: string | null;
  } | null>(null);
  const POLLING_INTERVAL = 30 * 1000; // Poll every 30s.

  const handleClick = () => {
    if (status === null) {
      // Start activity research.
      setStatus(LinkedInActivityParsingResult.SCHEDULED);
    }
  };

  if (parsedHTML) {
    console.log("parsed HTML: ", parsedHTML);
  }

  useEffect(() => {
    switch (status) {
      case LinkedInActivityParsingResult.SCHEDULED:
        startLinkedInActivityParsing(linkedInUrl)
          .then((response) => {
            setStatus(response.status);
            setTabId(response.tab_id);
          })
          .catch((error) => {
            setErrorMessage((error as Error).message);
            setStatus(null);
          });
        break;
      case LinkedInActivityParsingResult.IN_PROGRESS:
        if (!tabId) {
          setErrorMessage(
            `Tab Id missing for URL: ${linkedInUrl}, cannot check parsing status`
          );
          return;
        }
        const intervalId = setTimeout(async () => {
          getLinkedInActivityParsingResult(tabId, linkedInUrl)
            .then((response) => {
              if (response.status === LinkedInActivityParsingResult.COMPLETE) {
                // Parsing is complete.
                setParsedHTML(response.parsed_data);
                setStatus(null);
                setTabId(null);
                setErrorMessage(null);
              }
            })
            .catch((error) => {
              setErrorMessage((error as Error).message);
              setStatus(null);
            });
        }, POLLING_INTERVAL);
        return () => clearTimeout(intervalId);
      default:
      // Do nothing.
    }
  }, [status]);

  return (
    <div>
      {errorMessage && <p className="text-destructive">{errorMessage}</p>}
      <Button className="w-fit" onClick={handleClick}>
        Click me
      </Button>
    </div>
  );
};

export default LeadActivityParser;
