// src/components/custom-columns/ResponseConfigInput.tsx
import React from "react";
import { useFormContext, useWatch, useFieldArray } from "react-hook-form";
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { CreateCustomColumnRequest } from "@/services/CustomColumn";

const ResponseConfigInput: React.FC = () => {
  const { control } = useFormContext<CreateCustomColumnRequest>();
  const responseType = useWatch({ control, name: "response_type" });

  // Field Array for Enum 'allowed_values'
  const { fields, append, remove } = useFieldArray<CreateCustomColumnRequest>({
    control,
    name: "response_config.allowed_values" as never,
  });

  // --- Render logic based on responseType ---

  if (responseType === "enum") {
    return (
      <FormItem>
        <FormLabel>Allowed Values *</FormLabel>
        <FormDescription>
          Define the possible values for this Enum column.
        </FormDescription>
        <div className="flex flex-col gap-2">
          {fields.map((field, index) => (
            <FormField
              key={field.id}
              control={control}
              name={`response_config.allowed_values.${index}`}
              render={({ field: itemField }) => (
                <FormItem className="flex items-center gap-2">
                  <FormControl>
                    <Input
                      placeholder={`Value ${index + 1}`}
                      className="border-gray-300 flex-grow"
                      {...itemField}
                    />
                  </FormControl>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => remove(index)}
                    className="text-red-500 hover:bg-red-50 flex-shrink-0"
                  >
                    <Trash2 size={16} />
                  </Button>
                  <FormMessage className="text-xs mt-0" />{" "}
                  {/* Add FormMessage here */}
                </FormItem>
              )}
            />
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => append("")}
            className="mt-2 w-fit border-dashed"
          >
            + Add Value
          </Button>
        </div>
        <FormMessage /> {/* Message for the overall allowed_values array */}
      </FormItem>
    );
  }

  // Add inputs for other response_types if needed based on your backend docs
  // Example for 'string' (if backend supports it)
  /*
    if (responseType === 'string') {
        return (
            <>
                <FormField control={control} name="response_config.max_length" render={...} />
                <FormField control={control} name="response_config.tone" render={...} />
            </>
        );
    }
    */

  // No specific config needed for 'string', 'boolean', 'number', 'json_object' in this example
  return null;
};

export default ResponseConfigInput;
