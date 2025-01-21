import { PersonalityTrait } from "@/services/Leads";

const PersonalityTraitsView: React.FC<{
  personalityTrait: PersonalityTrait;
}> = ({ personalityTrait }) => {
  return (
    <div className="flex flex-col gap-4 px-2 py-0">
      <div className="flex flex-col gap-2">
        <p className="text-md font-semibold">Description</p>
        <p className="text-sm">{personalityTrait.description}</p>
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-md font-semibold">Evidence</p>
        {personalityTrait.evidence.map((evidence) => (
          <p key={evidence} className="text-sm">
            * {evidence}
          </p>
        ))}
      </div>
    </div>
  );
};

export default PersonalityTraitsView;
