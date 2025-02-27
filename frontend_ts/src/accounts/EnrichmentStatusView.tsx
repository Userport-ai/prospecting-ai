import { formatDate } from "@/common/utils";
import { Progress } from "@/components/ui/progress";
import { EnrichmentStatus } from "@/services/Common";
import { Link } from "react-router";

const CompletedStatusView: React.FC<{
  accountId: string;
  enrichmentStatus: EnrichmentStatus;
}> = ({ accountId, enrichmentStatus }) => {
  // Enrichment complete, link to Leads table on click
  const url = `/accounts/${accountId}/leads`;
  return (
    <div className="flex flex-col gap-2">
      <Link to={url} className="text-blue-500 underline font-medium">
        Complete
      </Link>
      <p className="text-xs">
        Last Updated: <span>{formatDate(enrichmentStatus.last_update)}</span>
      </p>
    </div>
  );
};

const InProgressStatusView: React.FC<{
  enrichmentStatus: EnrichmentStatus;
}> = ({ enrichmentStatus }) => {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-yellow-600 font-medium">In Progress</p>
      <p className="text-xs">
        Last Updated: <span>{formatDate(enrichmentStatus.last_update)}</span>
      </p>
      <Progress value={enrichmentStatus.avg_completion_percent} />
    </div>
  );
};

const FailedStatusView: React.FC<{
  enrichmentStatus: EnrichmentStatus;
}> = ({ enrichmentStatus }) => {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-red-700 font-medium">Failed</p>
      <p className="text-xs">
        Last Updated: <span>{formatDate(enrichmentStatus.last_update)}</span>
      </p>
    </div>
  );
};

const ScheduledStatusView: React.FC<{
  enrichmentStatus: EnrichmentStatus;
}> = ({ enrichmentStatus }) => {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-red-950 font-medium">Scheduled</p>
      <p className="text-xs">
        Last Updated: <span>{formatDate(enrichmentStatus.last_update)}</span>
      </p>
    </div>
  );
};

const EnrichmentStatusView: React.FC<{
  accountId: string;
  enrichmentStatus: EnrichmentStatus;
}> = ({ accountId, enrichmentStatus }) => {
  if (enrichmentStatus.total_enrichments === 0) {
    return <ScheduledStatusView enrichmentStatus={enrichmentStatus} />;
  } else if (
    enrichmentStatus.total_enrichments === enrichmentStatus.completed
  ) {
    return (
      <CompletedStatusView
        accountId={accountId}
        enrichmentStatus={enrichmentStatus}
      />
    );
  } else if (enrichmentStatus.failed > 0) {
    return <FailedStatusView enrichmentStatus={enrichmentStatus} />;
  }

  // In progress.
  return <InProgressStatusView enrichmentStatus={enrichmentStatus} />;
};

export default EnrichmentStatusView;
