import { PersonalizationSignal } from "@/services/Leads";

const Signal: React.FC<{ signal: PersonalizationSignal }> = ({ signal }) => {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col">
        <p className="text-xl font-semibold">Signal</p>
        <p className="text-md">{signal.description}</p>
      </div>
      <div className="flex flex-col">
        <p className="text-md font-medium">Reason</p>
        <p className="text-sm">{signal.reason}</p>
      </div>
      <div className="flex flex-col">
        <p className="text-md font-medium">Outreach Message</p>
        <p className="text-sm">{signal.outreach_message}</p>
      </div>
    </div>
  );
};

const PersonalizationSignalsView: React.FC<{
  personalizationSignals: PersonalizationSignal[];
}> = ({ personalizationSignals }) => {
  return (
    <div className="flex flex-col gap-8">
      {personalizationSignals.map((signal) => (
        <Signal key={signal.description} signal={signal} />
      ))}
    </div>
  );
};

export default PersonalizationSignalsView;
