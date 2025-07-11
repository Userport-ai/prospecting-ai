import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Cpu } from "lucide-react";
import { Progress } from "@/components/ui/progress";

export interface CustomColumnInput {
  query: string;
  format: string;
  columnName: string;
  rowIds?: string[];
}

// Get Display Name of the given custom column's key.
// For example, if the key is "target_market", we return "Target Market".
export const getCustomColumnDisplayName = (columnKey: string | null) => {
  if (columnKey === null) {
    return "";
  }
  return columnKey
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

const AddCustomColumn: React.FC<{
  onAdded: (formInput: CustomColumnInput) => void;
}> = ({ onAdded }) => {
  const [step, setStep] = useState(1);
  const [open, setOpen] = useState(false);

  // Dynamic Zod schema based on step
  const formSchema = z.object({
    query: z.string().min(1, "Query is required"),
    format: z.string().min(step > 1 ? 1 : 0, "Format is required"),
    columnName: z.string().min(step > 2 ? 1 : 0, "Column name is required"),
  });

  const defaultValues: CustomColumnInput = {
    query: "",
    format: "",
    columnName: "",
  };
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: defaultValues,
  });

  const handleNext = (updatedFormData: CustomColumnInput) => {
    if (step < 4) {
      setStep(step + 1);
    } else {
      onAdded(updatedFormData);
      form.reset();
      setStep(1);
      setOpen(false);
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  return (
    <div>
      {/* Trigger Button */}
      <Button
        onClick={() => setOpen(true)}
        variant={"outline"}
        className="flex gap-2 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300 border-gray-200"
      >
        <Cpu />
        Ask AI
      </Button>

      {/* Dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-gray-800 text-lg font-medium">
              Ask AI
            </DialogTitle>
            <DialogDescription></DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleNext)}>
              {/* Progress Indicator */}
              <p className="text-sm text-gray-500 mb-2">Progress</p>
              <Progress value={(step / 4) * 100} className="mb-4" />

              {/* Step Content */}
              <div className="flex flex-col gap-6">
                {/* Step 1: Query */}
                {(step === 1 || step === 4) && (
                  <FormField
                    control={form.control}
                    name="query"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-gray-800">Query</FormLabel>
                        <FormDescription className="text-gray-500 text-sm">
                          Enter a query that AI will use to provide answers for
                          each row.
                        </FormDescription>
                        <FormControl>
                          <Textarea
                            placeholder="e.g., What is the company's latest product?"
                            className="border-gray-300 rounded-md"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}

                {/* Step 2: Format */}
                {(step === 2 || step === 4) && (
                  <FormField
                    control={form.control}
                    name="format"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-gray-800">
                          Answer Format
                        </FormLabel>
                        <FormDescription className="text-gray-500 text-sm">
                          Choose the desired format for the answer.
                        </FormDescription>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                        >
                          <FormControl>
                            <SelectTrigger className="w-48 border-border">
                              <SelectValue placeholder="Select Format" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="text">Text</SelectItem>
                            <SelectItem value="yes-no">Yes/No</SelectItem>
                            <SelectItem value="number">Number</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />

                        {/* Format Helper Text */}
                        {field.value && (
                          <p className="text-gray-500 text-sm mt-2">
                            {field.value === "text" &&
                              "Answers will be in text format. If AI can't find an answer, you'll see 'Unknown'."}
                            {field.value === "yes-no" &&
                              "Answers will be 'Yes' or 'No'. If AI can't find an answer, you'll see 'Unknown'."}
                            {field.value === "number" &&
                              "Answers will be numeric values. If AI can't find an answer, you'll see 'Unknown'."}
                          </p>
                        )}
                      </FormItem>
                    )}
                  />
                )}

                {/* Step 3: Column Name */}
                {step >= 3 && (
                  <FormField
                    control={form.control}
                    name="columnName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-gray-800">
                          Column Name
                        </FormLabel>
                        <FormDescription className="text-gray-500 text-sm">
                          Specify a name for the new column in the table.
                        </FormDescription>
                        <FormControl>
                          <Input
                            placeholder="e.g., Product Launches"
                            className="border-gray-300 rounded-md"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </div>

              {/* Footer Navigation */}
              <DialogFooter className="mt-6">
                <div className="flex justify-between w-full">
                  {step > 1 && (
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={handleBack}
                    >
                      Back
                    </Button>
                  )}
                  <Button type="submit">{step < 4 ? "Next" : "Submit"}</Button>
                </div>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AddCustomColumn;
