import { Button } from "@/components/ui/button";
import {
  LinkedInActivityParsingStatus,
  startLinkedInActivityParsing,
} from "@/services/Extension";
import { useEffect, useState } from "react";

// Parses LinkedIn Activity for given Lead's LinkedIn URL.
const LeadActivityParser: React.FC<{ leadLinkedInUrl: string }> = ({
  leadLinkedInUrl,
}) => {
  const [linkedInUrl, setLinkedInUrl] = useState<string>(leadLinkedInUrl);
  const [status, setStatus] = useState<LinkedInActivityParsingStatus | null>(
    null
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const POLLING_INTERVAL = 30 * 1000; // Poll every 30s.

  const handleClick = () => {
    if (status === null) {
      // Start activity research.
      setStatus(LinkedInActivityParsingStatus.SCHEDULED);
    }
  };

  console.log("activity status: ", status);

  useEffect(() => {
    switch (status) {
      case LinkedInActivityParsingStatus.SCHEDULED:
        startLinkedInActivityParsing(linkedInUrl)
          .then((response) => setStatus(response.status))
          .catch((error) => {
            setErrorMessage(error);
            // Reset parsing status.
            setStatus(null);
          });
        break;
      case LinkedInActivityParsingStatus.IN_PROGRESS:
        const intervalId = setTimeout(async () => {
          //   const newPolledAccounts = await listAccounts(authContext, pollAccountIds);
          //   onPollingComplete(newPolledAccounts);
        }, POLLING_INTERVAL);
        return () => clearTimeout(intervalId);
        break;
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
