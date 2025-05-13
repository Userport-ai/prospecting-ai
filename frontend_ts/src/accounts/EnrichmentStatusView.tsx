import { useAuthContext } from "@/auth/AuthProvider";
import { formatDate } from "@/common/utils";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import { triggerLeadGeneration } from "@/services/Accounts";
import {
  EnrichmentStatus,
  EnrichmentStatusDetail,
  EnrichmentStatusEnum,
  EnrichmentType,
} from "@/services/Common";
import { Loader2, PlayCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

const GenerateLeadsButton: React.FC<{
  accountId: string;
  onLeadGenTriggered: () => void;
}> = ({ accountId, onLeadGenTriggered }) => {
  const authContext = useAuthContext();
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const onClick = async () => {
    setLoading(true);
    try {
      await triggerLeadGeneration(authContext, accountId);

      // Callback to refresh accounts table.
      // We don't set loading to false again, will let the
      // accounts table refresh update the UI to show lead gen progress.
      onLeadGenTriggered();
    } catch (error) {
      console.error("Failed to trigger lead generation with error: ", error);
      // Show toast.
      toast({
        variant: "destructive",
        title: "Uh oh! Something went wrong.",
        description:
          "Could not trigger lead generation, please contact support!",
      });
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-row gap-2">
      <p className="min-w-[5rem] text-sm text-gray-700 ">Leads:</p>
      {loading ? (
        <Loader2 className="h-4 w-4 mr-2 animate-spin text-purple-400" />
      ) : (
        <PlayCircle
          className="text-purple-400 hover:cursor-pointer"
          size={18}
          onClick={onClick}
        />
      )}
    </div>
  );
};

const CompletedStatusView: React.FC<{
  accountId: string;
  detail: EnrichmentStatusDetail;
}> = ({ accountId, detail }) => {
  if (detail.enrichment_type === EnrichmentType.GENERATE_LEADS) {
    // Link to Leads table on click
    const url = `/accounts/${accountId}/leads`;
    return (
      <Link to={url} className="text-blue-500 underline font-medium">
        Complete
      </Link>
    );
  }

  // For other enrichment types, just display Complete text.
  return <p className="text-sm text-blue-800 font-medium">Complete</p>;
};

const InProgressStatusView: React.FC<{
  detail: EnrichmentStatusDetail;
}> = ({ detail }) => {
  const completion_percent =
    detail.completion_percent !== null ? detail.completion_percent : 0;
  return (
    <div className="flex flex-col justify-center">
      <Progress value={completion_percent} className="w-[4rem] bg-gray-200" />
    </div>
  );
};

const FailedStatusView: React.FC<{}> = () => {
  return <p className="text-red-700 font-medium">Failed</p>;
};

const ScheduledStatusView: React.FC<{}> = () => {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-red-950 font-medium">Scheduled</p>
    </div>
  );
};

interface StatusViewProps {
  accountId: string;
  detail: EnrichmentStatusDetail;
}

const StatusView: React.FC<StatusViewProps> = ({ accountId, detail }) => {
  if (detail.status === EnrichmentStatusEnum.COMPLETED) {
    return <CompletedStatusView accountId={accountId} detail={detail} />;
  }
  if (detail.status === EnrichmentStatusEnum.FAILED) {
    return <FailedStatusView />;
  }
  return <InProgressStatusView detail={detail} />;
};

interface EnrichmentDetailViewProps {
  accountId: string;
  detail: EnrichmentStatusDetail;
}

const EnrichmentDetailView: React.FC<EnrichmentDetailViewProps> = ({
  accountId,
  detail,
}) => {
  const enrichmentTypeLabel =
    detail.enrichment_type === EnrichmentType.COMPANY_INFO
      ? "Account"
      : detail.enrichment_type === EnrichmentType.GENERATE_LEADS
      ? "Leads"
      : "Unknown";
  return (
    <div className="flex">
      <p className="min-w-[5rem] text-sm text-gray-700 ">
        {enrichmentTypeLabel}:
      </p>
      <StatusView accountId={accountId} detail={detail} />
    </div>
  );
};

const EnrichmentStatusView: React.FC<{
  accountId: string;
  enrichmentStatus: EnrichmentStatus;
  onLeadGenTriggered: () => void; // Callback once lead generation is successfully triggered.
}> = ({ accountId, enrichmentStatus, onLeadGenTriggered }) => {
  if (!enrichmentStatus.statuses) {
    // Enrichment is scheduled.
    return <ScheduledStatusView />;
  }

  // Sort so that leads status is always first.
  const enrichmentStatuses = enrichmentStatus.statuses
    .slice()
    .sort((s1, _) =>
      s1.enrichment_type === EnrichmentType.GENERATE_LEADS ? -1 : 1
    );

  const enrichmentsInProgress =
    enrichmentStatus.in_progress > 0 || enrichmentStatus.pending > 0;

  // Check if lead enrichment is missing.
  const isLeadEnrichmentMissing =
    enrichmentStatus.statuses.find(
      (detail) => detail.enrichment_type === EnrichmentType.GENERATE_LEADS
    ) === undefined;

  return (
    <div className="flex flex-col gap-2">
      {enrichmentStatuses.map((detail) => {
        return (
          <EnrichmentDetailView
            key={detail.enrichment_type}
            accountId={accountId}
            detail={detail}
          />
        );
      })}
      {isLeadEnrichmentMissing && (
        <GenerateLeadsButton
          accountId={accountId}
          onLeadGenTriggered={onLeadGenTriggered}
        />
      )}
      {enrichmentsInProgress && (
        <div className="flex flex-col text-xs text-gray-600">
          <p>Last Updated:</p>
          <p>{formatDate(enrichmentStatus.last_update)}</p>
        </div>
      )}
    </div>
  );
};

export default EnrichmentStatusView;
