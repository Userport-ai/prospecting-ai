import MarkdownRenderer from "@/common/MarkdownRenderer";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CustomColumnValueData } from "@/services/CustomColumn";
import { Info } from "lucide-react";

const RationaleTooltip = ({ rationale }: { rationale: string | null }) => {
  if (!rationale) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info
          size={14}
          className="ml-1 text-gray-400 hover:text-gray-600 cursor-pointer"
        />
      </TooltipTrigger>
      <TooltipContent
        className="max-w-xs p-2 bg-gray-800 text-white rounded text-xs"
        side="top"
      >
        <p className="font-semibold mb-1">Rationale:</p>
        <p>{rationale}</p>
      </TooltipContent>
    </Tooltip>
  );
};

const renderValueWithTooltip = (
  valueElement: React.ReactNode,
  rationale: string | null
) => {
  return (
    <div className="flex items-center">
      {valueElement}
      <RationaleTooltip rationale={rationale} />
    </div>
  );
};

interface CustomColumnValueRenderProps {
  customColumnValueData?: CustomColumnValueData | null;
}

const CustomColumnValueRender: React.FC<CustomColumnValueRenderProps> = ({
  customColumnValueData,
}) => {
  if (
    !customColumnValueData ||
    customColumnValueData.value === null ||
    customColumnValueData.value === undefined
  ) {
    return <span className="text-gray-400 italic">N/A</span>; // Or indicate loading/pending if applicable
  }

  switch (customColumnValueData.response_type) {
    case "enum":
      // Simple rendering for enum values - just display the string value
      return renderValueWithTooltip(
        <span className="whitespace-normal break-words">
          {String(customColumnValueData.value)}
        </span>,
        customColumnValueData.rationale
      );

    case "string":
      return renderValueWithTooltip(
        <div className="whitespace-normal break-words">
          <MarkdownRenderer content={String(customColumnValueData.value)} />
        </div>,
        customColumnValueData.rationale
      );

    case "number":
      return renderValueWithTooltip(
        <span>{Number(customColumnValueData.value).toLocaleString()}</span>, // Format number if needed
        customColumnValueData.rationale
      );

    case "boolean":
      return renderValueWithTooltip(
        <span>{customColumnValueData.value ? "Yes" : "No"}</span>, // Or use configured labels if available
        customColumnValueData.rationale
      );

    case "json_object":
      // Render a simplified view or a button to show details
      return renderValueWithTooltip(
        <span className="text-blue-600 italic cursor-pointer">
          [JSON Data]
        </span>, // Placeholder
        customColumnValueData.rationale // You might want a different way to show JSON rationale
      );

    default:
      return renderValueWithTooltip(
        <span>{String(customColumnValueData.value)}</span>,
        customColumnValueData.rationale
      );
  }
};

export default CustomColumnValueRender;
