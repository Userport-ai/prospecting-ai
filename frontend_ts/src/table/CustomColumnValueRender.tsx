import React, { useState } from "react";
import MarkdownRenderer from "@/common/MarkdownRenderer";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CustomColumnValueData } from "@/services/CustomColumn";
import { Info, Play, Loader2, RefreshCw } from "lucide-react";
import { useAuthContext } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import JsonDataView from "@/components/common/JsonDataView";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

// Import the function to trigger generation
import { generateCustomColumnValues } from "@/services/CustomColumn";
import { regenCustomColumnBtnDataId } from "@/common/utils";

// Helper to remove markdown backticks so that the Markdown renderer
// does not render it as a Code block. This is needed because LLM
// hallucinates these backticks.
const removeMarkdownBackticks = (text: string | null) => {
  if (!text) {
    return "";
  }
  if (text.startsWith("```markdown")) {
    text = text.split("markdown").join("");
  }
  // Replace all backticks.
  return text.split("```").join("");
};

// Button to regenerate custom column.
const RegenCustomColumnButton: React.FC<{ onClick: () => void }> = ({
  onClick,
}) => {
  return (
    <div className="mt-6 mb-2 flex justify-end">
      <Button
        data-id={regenCustomColumnBtnDataId}
        variant="ghost"
        size="sm"
        className="text-muted-foreground hover:text-blue-600 hover:bg-transparent"
        onClick={onClick}
      >
        <RefreshCw className="mr-1 h-4 w-4" />
        Regenerate
      </Button>
    </div>
  );
};

const RationaleAccordion: React.FC<{ rationale: string | null }> = ({
  rationale,
}) => {
  return (
    <Accordion type="single" collapsible className="w-full">
      <AccordionItem value="item-1">
        <AccordionTrigger>Rationale</AccordionTrigger>
        <AccordionContent>
          {" "}
          <MarkdownRenderer content={removeMarkdownBackticks(rationale)} />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

const renderValueWithRationale = (
  valueElement: React.ReactNode,
  rationale: string | null,
  onRegen: () => void
) => {
  return (
    <div className="flex-col justify-center">
      {valueElement}
      <RationaleAccordion rationale={rationale} />
      <RegenCustomColumnButton onClick={onRegen} />
    </div>
  );
};

interface CustomColumnValueRenderProps {
  customColumnValueData?: CustomColumnValueData | null;
  entityId?: string; // ID of the account/lead this column value is for
  onValueGenerated?: () => void; // Callback after successful generation
  disableGeneration: boolean; // Whether to disable generation. For example, when enrichment is in progress.
}

const CustomColumnValueRender: React.FC<CustomColumnValueRenderProps> = ({
  customColumnValueData,
  entityId,
  onValueGenerated,
  disableGeneration,
}) => {
  const [isGenerating, setIsGenerating] = useState(
    customColumnValueData &&
      customColumnValueData.status &&
      (customColumnValueData.status === "processing" ||
        customColumnValueData.status === "pending")
  );
  const [generationError, setGenerationError] = useState<string | null>(null);
  const authContext = useAuthContext();

  // Function to trigger the generation of values
  const handleGenerateValue = async () => {
    if (!customColumnValueData || !entityId) return;

    // Check if columnId is available
    if (!customColumnValueData.columnId) {
      console.error("Column ID is missing from customColumnValueData");
      setGenerationError("Column ID is missing");
      return;
    }

    setIsGenerating(true);
    setGenerationError(null);

    try {
      // Call the API to generate the custom column value
      await generateCustomColumnValues(
        authContext,
        customColumnValueData.columnId,
        [entityId]
      );

      // If onValueGenerated callback is provided, call it
      if (onValueGenerated) {
        onValueGenerated();
      }
    } catch (error) {
      console.error("Error generating custom column value:", error);
      setGenerationError(
        error instanceof Error ? error.message : "Failed to generate value"
      );
    } finally {
      // If no callback is provided, we still need to clear the loading state
      // Otherwise, the component will be rerendered when data is refreshed
      if (!onValueGenerated) {
        setIsGenerating(false);
      }
    }
  };

  // If no value data is available or value is null/undefined, show the generate button
  if (
    !customColumnValueData ||
    customColumnValueData.value === null ||
    customColumnValueData.value === undefined
  ) {
    // For the case where there's no customColumnValueData at all, we need to ensure we have a columnId
    // This button will only appear if both entityId and columnId are available
    const hasRequiredIds = entityId && customColumnValueData?.columnId;

    return (
      <div className="flex items-center">
        {isGenerating ? (
          <div className="flex items-center text-gray-500">
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            <span className="text-xs">Generating...</span>
          </div>
        ) : hasRequiredIds ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={disableGeneration}
            onClick={handleGenerateValue}
            className="flex items-center text-blue-600 hover:text-blue-800 hover:bg-blue-50 p-1"
          >
            <Play className="h-4 w-4 mr-1" />
            <span className="text-xs">Generate</span>
          </Button>
        ) : (
          <span className="text-gray-400 italic text-xs">N/A</span>
        )}
        {generationError && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Info size={14} className="ml-1 text-red-500 cursor-pointer" />
            </TooltipTrigger>
            <TooltipContent className="bg-red-50 border border-red-200 text-red-800 p-2">
              {generationError}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
    );
  }

  // Render based on response type
  switch (customColumnValueData.response_type) {
    case "string":
      return renderValueWithRationale(
        <div className="max-w-full whitespace-normal break-words">
          <MarkdownRenderer
            content={removeMarkdownBackticks(
              String(customColumnValueData.value)
            )}
          />
        </div>,
        customColumnValueData.rationale,
        handleGenerateValue
      );

    case "number":
      return renderValueWithRationale(
        <span>{Number(customColumnValueData.value).toLocaleString()}</span>, // Format number if needed
        customColumnValueData.rationale,
        handleGenerateValue
      );

    case "enum":
      // Simple rendering for enum values - just display the string value
      return renderValueWithRationale(
        <span className="whitespace-normal break-words">
          {String(customColumnValueData.value)}
        </span>,
        customColumnValueData.rationale,
        handleGenerateValue
      );

    case "boolean":
      return renderValueWithRationale(
        <span>{customColumnValueData.value ? "Yes" : "No"}</span>, // Or use configured labels if available
        customColumnValueData.rationale,
        handleGenerateValue
      );

    case "json_object":
      // Render an expandable JSON view
      return renderValueWithRationale(
        <JsonDataView
          data={customColumnValueData.value as object}
          initialExpanded={false}
        />,
        customColumnValueData.rationale,
        handleGenerateValue
      );

    default:
      return renderValueWithRationale(
        <span>{String(customColumnValueData.value)}</span>,
        customColumnValueData.rationale,
        handleGenerateValue
      );
  }
};

export default CustomColumnValueRender;
