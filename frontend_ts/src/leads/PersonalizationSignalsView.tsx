import { PersonalizationSignal } from "@/services/Leads";

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

const Signal: React.FC<{ signal: PersonalizationSignal }> = ({ signal }) => {
  return (
    <div className="flex flex-col gap-1">
      <LabelValuePair label="Signal" value={signal.description} />
      <LabelValuePair label="Reason" value={signal.reason} />
      <LabelValuePair
        label="Outreach Message"
        value={signal.outreach_message}
      />
    </div>
  );
};

const PersonalizationSignalsView: React.FC<{
  personalizationSignals: PersonalizationSignal[];
}> = ({ personalizationSignals }) => {
  return (
    <div className="flex flex-col gap-4">
      {personalizationSignals.map((signal) => (
        <Signal key={signal.description} signal={signal} />
      ))}
    </div>
  );
};

export default PersonalizationSignalsView;
