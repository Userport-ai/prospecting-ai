import { RecentCompanyEvent } from "@/services/Common";

const RecentCompanyEventsView: React.FC<{
  recentEvents: RecentCompanyEvent[];
}> = ({ recentEvents }) => {
  if (recentEvents.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-6">
      {recentEvents.map((rEvent) => (
        <div key={rEvent.title} className="flex flex-col">
          <p className="text-md text-gray-800">{rEvent.title}</p>
          <a
            href={rEvent.source}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs hover:underline text-blue-600"
          >
            {rEvent.source}
          </a>
          <p className="text-xs text-gray-500">{rEvent.date}</p>
          <p className="text-sm text-gray-700">{rEvent.description}</p>
        </div>
      ))}
    </div>
  );
};

export default RecentCompanyEventsView;
