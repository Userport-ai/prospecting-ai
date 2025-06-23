// src/components/custom-columns/CreateCustomColumnDialog.tsx
import React, { useEffect, useState } from "react";
import { DialogProps } from "@radix-ui/react-dialog";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox"; // For Is Active & Context Types
import {
  CreateCustomColumnRequest,
  createCustomColumn,
  CustomColumn,
  updateCustomColumn,
} from "@/services/CustomColumn";
import { useAuthContext } from "@/auth/AuthProvider"; // Adjust path
import ResponseConfigInput from "./ResponseConfigInput";
import { Separator } from "../ui/separator";
import { Loader2 } from "lucide-react";

export enum EntityType {
  ACCOUNT = "account",
  LEAD = "lead",
}

// --- Zod Schema ---
// Making response_config optional initially and refining based on response_type
const baseSchema = z.object({
  name: z.string().min(1, "Column Name is required."),
  question: z.string().min(1, "Question is required."),
  entity_type: z.enum([EntityType.ACCOUNT, EntityType.LEAD]),
  response_type: z.enum(["string", "json_object", "boolean", "number", "enum"]),
  response_config: z
    .object({
      allowed_values: z
        .array(z.string().min(1, "Enum value cannot be empty."))
        .optional(),
      // Add other response_config fields here if needed
    })
    .optional(),
  ai_config: z.object({
    model: z.string().min(1, "AI Model is required."),
    temperature: z.coerce.number().min(0).max(1), // Coerce to number, validate range
    use_internet: z.boolean().optional(),
    unstructured_response: z.boolean().optional(),
    validate_with_search: z.boolean().optional(),
    use_linkedin_activity: z.boolean().optional(),
  }),
  context_type: z
    .array(z.string())
    .min(1, "At least one Context Type is required."),
  refresh_interval: z.coerce.number().int().positive().optional().nullable(), // Optional integer > 0
  is_active: z.boolean().optional(),
});

// Refine schema for enum response_type
const refinedSchema = baseSchema.refine(
  (data) => {
    if (data.response_type === "enum") {
      return (
        data.response_config?.allowed_values &&
        data.response_config.allowed_values.length >= 1
      );
    }
    return true;
  },
  {
    message:
      "Allowed Values are required for Enum type and must contain at least one value.",
    path: ["response_config.allowed_values"], // Point error to the correct field
  }
);

// --- Available Context Types (Adjust based on your actual backend options) ---
const AVAILABLE_CONTEXT_TYPES = [
  { id: "company_profile", label: "Company Profile" },
  { id: "lead_activity", label: "Lead Activity" },
  { id: "recent_news", label: "Recent News" },
  { id: "website_data", label: "Website Data" },
];

// --- Available AI Models (Adjust as needed) ---
const AVAILABLE_AI_MODELS = [
  "gemini-2.5-pro-preview-05-06",
  "gemini-2.5-flash-preview-04-17",
  "gpt-4.1",
  "gpt-4.1-mini",
  "gpt-4o",
  "gpt-4o-mini",
];

// --- Component Props ---
interface CreateOrEditCustomColumnDialogProps extends DialogProps {
  customColumn: CustomColumn | null; // Existing custom column value if edit mode else null in create mode.
  entityType: EntityType;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (newColumn: CustomColumn) => Promise<void>; // Callback on successful creation
}

// --- The Component ---
const CreateOrEditCustomColumnDialog: React.FC<
  CreateOrEditCustomColumnDialogProps
> = ({ customColumn, entityType, open, onOpenChange, onSuccess }) => {
  const authContext = useAuthContext();
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Populate default values using existing custom column (edit mode) if it exists.
  const defaultValues: CreateCustomColumnRequest = {
    name: customColumn?.name ?? "",
    question: customColumn?.question ?? "",
    entity_type: customColumn?.entity_type ?? entityType,
    response_type: customColumn?.response_type ?? "string",
    response_config: customColumn?.response_config ?? { allowed_values: [] },
    ai_config: customColumn?.ai_config ?? {
      model: AVAILABLE_AI_MODELS[0],
      temperature: 0.1,
      use_internet: false,
      unstructured_response: false,
      use_linkedin_activity: false,
      validate_with_search: false,
    },
    context_type: customColumn?.context_type ?? [AVAILABLE_CONTEXT_TYPES[0].id], // Default context
    refresh_interval: customColumn?.refresh_interval ?? 24 * 7, // Default to weekly
    is_active: customColumn?.is_active ?? true,
  };

  const form = useForm<CreateCustomColumnRequest>({
    resolver: zodResolver(refinedSchema),
    defaultValues: defaultValues,
  });

  const submitBtnName =
    customColumn === null ? "Create Column" : "Update Column";

  // Reset form when dialog opens or closes or custom column value changes.
  useEffect(() => {
    if (open) {
      form.reset(defaultValues);
    } else {
      form.reset();
    }
    setApiError(null);
  }, [open, customColumn, form]);

  const onSubmit = async (data: CreateCustomColumnRequest) => {
    setLoading(true);
    setApiError(null);

    try {
      var newColumn: CustomColumn;
      if (customColumn === null) {
        newColumn = await createCustomColumn(authContext, data);
      } else {
        // Hack: Manual deletion of response_config key so that we don't run into
        // 400 validation error on the backend: {"response_config":["String response requires max_length as integer"]}.
        // TODO: fix on backend and then remove this code.
        delete data.response_config;
        newColumn = await updateCustomColumn(
          authContext,
          customColumn.id,
          data
        );
      }
      await onSuccess(newColumn);
      if (onOpenChange) onOpenChange(false); // Close dialog on success
    } catch (error: any) {
      console.error("Failed to create custom column:", error);
      setApiError(error.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[50rem] max-h-[90vh] overflow-y-auto">
        <DialogHeader className="mb-2">
          <DialogTitle>Ask AI</DialogTitle>
          <DialogDescription>
            Powered by AI insights based on your question.
          </DialogDescription>
        </DialogHeader>

        {apiError && (
          <p className="text-sm text-red-600 bg-red-50 p-2 rounded border border-red-200">
            {apiError}
          </p>
        )}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Product Selection */}

            {/* Column Name */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  {" "}
                  <FormLabel>Column Name</FormLabel>
                  <FormControl>
                    <Input
                      className="border border-gray-300"
                      placeholder="e.g., Hiring for Cloud Engineer?"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription></FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            {/* Question */}
            <FormField
              control={form.control}
              name="question"
              render={({ field }) => (
                <FormItem>
                  {" "}
                  <FormLabel>Question</FormLabel>
                  <FormDescription>
                    The core instruction for the AI.
                  </FormDescription>
                  <FormControl>
                    <Textarea
                      className="border border-gray-300"
                      placeholder="e.g., Is the Account hiring for Cloud Engineers right now? Do not consider any job openings that are expired."
                      rows={6}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Response Type */}
            <FormField
              control={form.control}
              name="response_type"
              render={({ field }) => (
                <FormItem>
                  {" "}
                  <FormLabel>Response Type</FormLabel>
                  <FormDescription>
                    "Text" gives open-ended answers; "Number" returns score,
                    count etc.
                  </FormDescription>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger className="border border-gray-300">
                        <SelectValue placeholder="Select format..." />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="string">Text</SelectItem>
                      <SelectItem value="number">Number</SelectItem>
                      {/* <SelectItem value="boolean">Yes/No</SelectItem>
                      <SelectItem value="enum">Multiple Choice (Enum)
                      </SelectItem>
                      <SelectItem value="json_object">JSON Object</SelectItem> */}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Response Config (Conditional) for enum values. */}
            <ResponseConfigInput />

            <Separator />

            <FormField
              control={form.control}
              name="ai_config"
              render={({ field }) => (
                <div className="flex flex-col gap-3">
                  <p className="text-md font-medium text-gray-700">
                    Data Sources
                  </p>

                  <div className="flex flex-col gap-6">
                    <FormItem className="flex flex-row space-x-3 space-y-0">
                      <FormControl>
                        <Checkbox
                          className="size-4"
                          checked={field.value?.use_internet === true}
                          onCheckedChange={(checked) => {
                            field.onChange({
                              ...field.value,
                              use_internet: checked,
                              // Unstructured response and validate with search is set/unset whenever use_internet is set/unset.
                              unstructured_response: checked,
                              validate_with_search: checked,
                            });
                          }}
                        />
                      </FormControl>
                      <div className="flex flex-col gap-1 leading-none">
                        <FormLabel>Use Web Search</FormLabel>
                        <FormDescription>
                          Search the web to answer the question.
                        </FormDescription>
                      </div>
                      <FormMessage />
                    </FormItem>

                    {entityType === EntityType.LEAD && (
                      <FormItem className="flex flex-row space-x-3 space-y-0">
                        <FormControl>
                          <Checkbox
                            className="size-4"
                            checked={
                              field.value?.use_linkedin_activity === true
                            }
                            onCheckedChange={(checked) => {
                              field.onChange({
                                ...field.value,
                                use_linkedin_activity: checked,
                              });
                            }}
                          />
                        </FormControl>
                        <div className="flex flex-col gap-1 leading-none">
                          <FormLabel>Use LinkedIn Activity</FormLabel>
                          <FormDescription>
                            Use the Lead's Recent LinkedIn Activity to answer
                            the question.
                          </FormDescription>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  </div>
                </div>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange && onOpenChange(false)}
                disabled={loading}
                className="border border-gray-300"
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  submitBtnName
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export default CreateOrEditCustomColumnDialog;
