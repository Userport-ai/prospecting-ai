import { AreaOfInterest } from "@/services/Leads";

const AreasOfInterestView: React.FC<{ areasOfInterest: AreaOfInterest[] }> = ({
  areasOfInterest,
}) => {
  return (
    <div className="flex flex-col gap-4 px-2 py-0">
      {areasOfInterest.map((interest) => (
        <div key={interest.description} className="flex flex-col gap-2">
          <p className="text-md font-semibold">{interest.description}</p>
          {interest.supporting_activities.map((activity) => (
            <p key={activity} className="text-sm">
              {activity}
            </p>
          ))}
        </div>
      ))}
    </div>
  );
};

export default AreasOfInterestView;
