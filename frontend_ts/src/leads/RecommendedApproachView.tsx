import { RecommendedApproach } from "@/services/Leads";
import { Separator } from "@radix-ui/react-separator";

const LabelValuePair: React.FC<{ label: string; value: any }> = ({
  label,
  value,
}) => {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-md font-semibold">{label}</p>
      {!Array.isArray(value) ? (
        <p className="text-sm">{value}</p>
      ) : (
        value.map((v) => (
          <p key={v} className="text-sm">
            * {v}
          </p>
        ))
      )}
    </div>
  );
};

const RecommendedApproachView: React.FC<{
  recommendedApproach: RecommendedApproach;
}> = ({ recommendedApproach }) => {
  return (
    <div className="flex flex-col gap-4 px-2 py-0">
      <Separator />
      <LabelValuePair
        label="Approach"
        value={recommendedApproach.approach}
      ></LabelValuePair>
      <LabelValuePair
        label="Cautions"
        value={recommendedApproach.cautions}
      ></LabelValuePair>
      <LabelValuePair
        label="Key Topics"
        value={recommendedApproach.key_topics}
      ></LabelValuePair>
      <LabelValuePair
        label="Best Channels"
        value={recommendedApproach.best_channels}
      ></LabelValuePair>
      <LabelValuePair
        label="Timing Preferences"
        value={recommendedApproach.timing_preferences}
      ></LabelValuePair>
      <LabelValuePair
        label="Conversation Starters"
        value={recommendedApproach.timing_preferences}
      ></LabelValuePair>
    </div>
  );
};

export default RecommendedApproachView;
