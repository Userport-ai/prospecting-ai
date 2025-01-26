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
  return (
    <div
      className={cn(
        "flex flex-col whitespace-normal break-all",
        wrapColumnContentClass
      )}
    >
      {/* Total Funding Details */}
      <div className="flex flex-col gap-2 p-2 mb-4">
        <h2 className="text-md font-medium">Total Funding</h2>
        <Separator />
        <LabelValuePair
          label="Amount"
          value={fundingDetails.total_funding.amount}
        ></LabelValuePair>
        <LabelValuePair
          label="Currency"
          value={fundingDetails.total_funding.currency}
        ></LabelValuePair>
        <LabelValuePair
          label="As of Date"
          value={fundingDetails.total_funding.as_of_date ?? "Unknown"}
        ></LabelValuePair>
      </div>

      {/* Funding Rounds */}
      {fundingDetails.funding_rounds.map((fundingRound, idx) => (
        <div key={idx} className="flex flex-col gap-2 p-2">
          <h2 className="text-md font-medium">Round</h2>
          <Separator />
          <LabelValuePair
            label="Series"
            value={fundingRound.series}
          ></LabelValuePair>
          <LabelValuePair
            label="Amount"
            value={fundingRound.amount}
          ></LabelValuePair>
          <LabelValuePair
            label="Currency"
            value={fundingRound.currency}
          ></LabelValuePair>
          <LabelValuePair
            label="Lead Investors"
            value={fundingRound.lead_investors}
          ></LabelValuePair>
        </div>
      ))}
    </div>
  );
};

export default FundingDetailsView;
