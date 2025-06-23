import { wrapColumnContentClass } from "@/common/utils";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { FundingDetails } from "@/services/Accounts";

const LabelValuePair: React.FC<{ label: string; value: any }> = ({
  label,
  value,
}) => {
  return (
    <div className="flex gap-2">
      <p className="text-sm">{label}:</p>
      <p className="text-sm">{value}</p>
    </div>
  );
};

const FundingDetailsView: React.FC<{ fundingDetails: FundingDetails }> = ({
  fundingDetails,
}) => {
  // Check if total_funding exists
  const hasTotalFunding = fundingDetails?.total_funding != null;
  
  return (
    <div
      className={cn(
        "flex flex-col whitespace-normal break-all",
        wrapColumnContentClass
      )}
    >
      {/* Total Funding Details - Only show if total_funding exists */}
      {hasTotalFunding && (
        <div className="flex flex-col gap-2 p-2 mb-4">
          <h2 className="text-md font-medium">Total Funding</h2>
          <Separator />
          <LabelValuePair
            label="Amount"
            value={fundingDetails.total_funding.amount ?? "Unknown"}
          ></LabelValuePair>
          <LabelValuePair
            label="Currency"
            value={fundingDetails.total_funding.currency ?? "Unknown"}
          ></LabelValuePair>
          <LabelValuePair
            label="As of Date"
            value={fundingDetails.total_funding.as_of_date ?? "Unknown"}
          ></LabelValuePair>
        </div>
      )}

      {/* Funding Rounds - Only map if funding_rounds exists and is an array */}
      {fundingDetails?.funding_rounds?.length > 0 && 
        fundingDetails.funding_rounds.map((fundingRound, idx) => (
          <div key={idx} className="flex flex-col gap-2 p-2">
            <h2 className="text-md font-medium">Round</h2>
            <Separator />
            <LabelValuePair
              label="Series"
              value={fundingRound.series ?? "Unknown"}
            ></LabelValuePair>
            <LabelValuePair
              label="Amount"
              value={fundingRound.amount ?? "Unknown"}
            ></LabelValuePair>
            <LabelValuePair
              label="Currency"
              value={fundingRound.currency ?? "Unknown"}
            ></LabelValuePair>
            <LabelValuePair
              label="Lead Investors"
              value={fundingRound.lead_investors?.length > 0 ? fundingRound.lead_investors.join(", ") : "None"}
            ></LabelValuePair>
          </div>
        ))
      }
      
      {/* Show message if no funding data is available */}
      {(!hasTotalFunding && (!fundingDetails?.funding_rounds || fundingDetails.funding_rounds.length === 0)) && (
        <div className="p-2">
          <p className="text-sm text-gray-500">No funding details available</p>
        </div>
      )}
    </div>
  );
};

export default FundingDetailsView;
