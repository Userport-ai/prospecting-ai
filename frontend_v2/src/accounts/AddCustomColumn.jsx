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

function AddCustomColumn() {
  const [step, setStep] = useState(1);
  var formSchema;
  if (step === 1) {
    formSchema = z.object({
      query: z.string().min(1),
      format: z.string(),
      columnName: z.string(),
    });
  } else if (step === 2) {
    formSchema = z.object({
      query: z.string().min(1),
      format: z.string().min(1),
      columnName: z.string(),
    });
  } else if (step >= 3) {
    formSchema = z.object({
      query: z.string().min(1),
      format: z.string().min(1),
      columnName: z.string().min(1),
    });
  }

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      query: "",
      format: "",
      columnName: "",
    },
  });

  const [open, setOpen] = useState(false);

  const handleNext = (newFormData) => {
    if (step < 4) {
      setStep(step + 1);
      return;
    }
    // Submit form.
    console.log("Form data: ", newFormData);
    // TODO: Call server with given Form data as input.
    setOpen(false);
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  return (
    <div>
      <Button
        onClick={() => setOpen(true)}
        className="w-fit mt-2 bg-[rgb(136,102,221)]"
      >
        <Cpu />
        Ask AI
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-gray-600">Ask AI</DialogTitle>
            <DialogDescription></DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleNext)}>
              {/* Progress Indicator */}
              <p className="text-sm text-gray-400">Progress</p>
              <Progress value={(step / 4.0) * 100.0} />

              {/* Step Content */}
              <div className="flex flex-col mt-4 gap-4">
                {(step === 1 || step === 4) && (
                  <FormField
                    control={form.control}
                    name="query"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-gray-700">Query</FormLabel>
                        <FormDescription className="text-sm text-gray-500">
                          Your query will be answered by AI for each row in your
                          list.
                        </FormDescription>
                        <FormControl>
                          <Textarea
                            className="h-24 border border-gray-300"
                            placeholder="e.g., Has the company launched any products recently? Has this person attended any events recently?"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}

                {(step === 2 || step === 4) && (
                  <FormField
                    control={form.control}
                    name="format"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-gray-700">
                          Answer Format
                        </FormLabel>
                        <FormDescription className="text-sm text-gray-500">
                          Select the desired format of the answer.
                        </FormDescription>
                        <Select
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                        >
                          <FormControl>
                            <SelectTrigger className="w-[10rem]">
                              <SelectValue placeholder="Select Format" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="text">Text</SelectItem>
                            <SelectItem value="yes-no">Yes or No</SelectItem>
                            <SelectItem value="number">Number</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />

                        {/* Helper message for selected option */}
                        {field.value === "text" && (
                          <p className="text-sm text-gray-500">
                            Each row will be populated with a one ore more lines
                            of text as the answer. If AI could not find an
                            answer, you will see the answer as Unknown.
                          </p>
                        )}
                        {field.value === "yes-no" && (
                          <p className="text-sm text-gray-500">
                            Each row will be populated with a Yes or No as the
                            answer. If AI could not find an answer, you will see
                            the answer as Unknown.
                          </p>
                        )}
                        {field.value === "number" && (
                          <p className="text-sm text-gray-500">
                            Each row will be populated with a Number as the
                            answer. If AI could not find an answer, you will see
                            the answer as Unknown.
                          </p>
                        )}
                      </FormItem>
                    )}
                  />
                )}

                {step >= 3 && (
                  <FormField
                    control={form.control}
                    name="columnName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-gray-700">
                          Column Name
                        </FormLabel>
                        <FormDescription className="text-sm text-gray-500">
                          Enter the name of the new column in the table that
                          will store the answers.
                        </FormDescription>
                        <FormControl>
                          <Input
                            className="border border-gray-300"
                            placeholder="e.g., Events held, Products launched etc."
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </div>

              {/* Dialog Footer */}
              <DialogFooter className="mt-4">
                {step === 1 && (
                  <div className="justify-end">
                    <Button type="submit">Next</Button>
                  </div>
                )}
                {step > 1 && (
                  <div className="w-full flex justify-between">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={handleBack}
                    >
                      Back
                    </Button>
                    <Button type="submit">
                      {step < 4 ? "Next" : "Submit"}
                    </Button>
                  </div>
                )}
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default AddCustomColumn;
