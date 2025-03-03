import React, { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, UseFormReturn } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
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
import { Trash } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Product } from "@/services/Products";

interface RoleTitleFormFieldProps {
  form: UseFormReturn<Product>;
  fieldPath:
    | "persona_role_titles.buyers"
    | "persona_role_titles.influencers"
    | "persona_role_titles.end_users";
  formStepClassName: string;
  inputClassName: string;
}

const RoleTitleFormField: React.FC<RoleTitleFormFieldProps> = ({
  form,
  fieldPath,
  formStepClassName,
  inputClassName,
}) => {
  var labelName = "";
  var labelDescription = "";
  var roleTitlePlaceHolder = "";
  if (fieldPath === "persona_role_titles.buyers") {
    labelName = "Buyers *";
    labelDescription = "Add role titles of all Buyer personas";
    roleTitlePlaceHolder = "e.g. Director of Sales";
  } else if (fieldPath === "persona_role_titles.influencers") {
    labelName = "Influencers *";
    labelDescription = "Add role titles of all Influencer personas";
    roleTitlePlaceHolder = "e.g. Business Development Manager";
  } else if (fieldPath === "persona_role_titles.end_users") {
    labelName = "End Users *";
    labelDescription = "Add role titles of all End User personas";
    roleTitlePlaceHolder = "e.g. Business Developemnt Representative";
  }
  if (labelName === "") {
    console.log(`Invalid field path value: ${fieldPath}`);
    return null;
  }

  return (
    <FormField
      control={form.control}
      name={fieldPath}
      render={({ field }) => (
        <FormItem>
          <FormLabel className={formStepClassName}>{labelName}</FormLabel>
          <FormDescription className="text-sm text-gray-500">
            {labelDescription}
          </FormDescription>
          <FormControl>
            <div>
              {field.value.map((role, index) => (
                <div key={index} className="flex gap-2 items-center">
                  <Input
                    className={inputClassName}
                    value={role}
                    onChange={(e) => {
                      const updatedRoles = [...field.value];
                      updatedRoles[index] = e.target.value;
                      field.onChange(updatedRoles); // Update form field
                    }}
                    onBlur={() => {
                      if (!field.value[index].trim()) {
                        // Remove empty input on blur
                        const updatedRoles = field.value.filter(
                          (_, i) => i !== index
                        );
                        field.onChange(updatedRoles);
                      }
                    }}
                    placeholder={roleTitlePlaceHolder}
                  />
                  <Button
                    type="button"
                    className="p-2 text-red-500 font-bold border border-gray-300 bg-white"
                    onClick={() => {
                      const updatedRoles = field.value.filter(
                        (_, i) => i !== index
                      );
                      field.onChange(updatedRoles);
                    }}
                  >
                    X
                  </Button>
                </div>
              ))}
              <Button
                size="sm"
                type="button"
                className="mt-2 p-2 bg-purple-400 text-white rounded"
                onClick={() => {
                  if (field.value?.some((role) => !role.trim())) {
                    return; // Prevent adding a new input if any existing one is empty
                  }
                  field.onChange([...(field.value || []), ""]);
                }}
              >
                + Add Role
              </Button>
            </div>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

interface SignalsFormFieldProps {
  form: UseFormReturn<Product>;
  formStepClassName: string;
  inputClassName: string;
}

const SignalsFormField: React.FC<SignalsFormFieldProps> = ({
  form,
  formStepClassName,
  inputClassName,
}) => {
  const getSignalsList = (
    playbookDescription: string | undefined
  ): string[] => {
    if (!playbookDescription) {
      return [];
    }
    return playbookDescription.split("\n");
  };

  const toSignalsString = (signalsList: string[]) => {
    return signalsList.join("\n");
  };

  return (
    <FormField
      control={form.control}
      name="playbook_description"
      render={({ field }) => (
        <FormItem>
          <FormLabel className={formStepClassName}>Signals *</FormLabel>
          <FormDescription className="text-sm text-gray-500">
            You can add Signals that can be found on Lead's profile that make
            them relevant. Examples of Signals are keywords they may mention on
            their profile, use of certain technologies, use of certain
            competitors, past experiences etc. You can describe each signal as a
            sentence (Imagine prompting ChatGPT).
          </FormDescription>
          <FormControl>
            <div className="flex flex-col gap-2">
              {getSignalsList(field.value).map((signal, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    className={inputClassName}
                    value={signal}
                    onChange={(e) => {
                      const updatedRoles = [...getSignalsList(field.value)];
                      updatedRoles[index] = e.target.value;
                      field.onChange(toSignalsString(updatedRoles)); // Update form field
                    }}
                    placeholder="Enter a signal"
                  />
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon"
                    onClick={() => {
                      const updatedRoles = getSignalsList(field.value).filter(
                        (_, i) => i !== index
                      );
                      field.onChange(toSignalsString(updatedRoles));
                    }}
                  >
                    <Trash className="w-4 h-4" />
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                size="sm"
                className="w-fit mt-2 p-2 bg-purple-400 text-white rounded"
                onClick={() => {
                  if (
                    getSignalsList(field.value).some((role) => !role.trim())
                  ) {
                    return; // Prevent adding a new input if any existing one is empty
                  }
                  field.onChange(
                    toSignalsString([...getSignalsList(field.value), " "])
                  );
                }}
              >
                + Add Signal
              </Button>
            </div>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

interface ProductFormProps {
  product: Product;
  onSubmit: (addedProduct: Product) => void; // Type for the onClick callback
  onCancel: () => void;
}

const ProductForm: React.FC<ProductFormProps> = ({
  product,
  onSubmit,
  onCancel,
}) => {
  // State to manage the current step of the form
  const [step, setStep] = useState(1);

  const formSchema = z.object({
    name: z.string().min(1, "Name is required"),
    website:
      step > 1
        ? z.string().startsWith("https://", "Website must start with https://")
        : z.string(),
    description: z.string().min(step > 2 ? 1 : 0, "Description is required"),
    icp_description: z.string().min(step > 3 ? 1 : 0, "ICP is required"),
    persona_role_titles: z.object({
      buyers: z
        .array(z.string())
        .min(step > 4 ? 1 : 0, "Buyers input is required")
        .refine((values) => step <= 4 || values.every((v) => v.trim() !== ""), {
          message: "Each Buyer role must be non-empty",
        }),
      influencers: z
        .array(z.string())
        .min(step > 4 ? 1 : 0, "Influencers input is required")
        .refine((values) => step <= 4 || values.every((v) => v.trim() !== ""), {
          message: "Each Influencer role must be non-empty",
        }),
      end_users: z
        .array(z.string())
        .min(step > 4 ? 1 : 0, "End Users input is required")
        .refine((values) => step <= 4 || values.every((v) => v.trim() !== ""), {
          message: "Each End User role must be non-empty",
        }),
    }),
    playbook_description: z.string().min(0),
  });
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: product,
  });

  const lastStepNum: number = 7;
  const nextButtonText = step === lastStepNum ? "Submit" : "Next";
  const backButtonText = step === 1 ? "Cancel" : "Back";

  // Input and textarea base styles
  const inputClassName =
    "w-full rounded-lg border border-gray-300 bg-white py-2 px-4 placeholder-gray-400 focus:border-primary focus:ring-2 focus:ring-primary shadow-sm";

  const formStepClassName = "text-gray-700 text-md font-semibold";

  // Handle user clicking next on form.
  const onNext = (addedProduct: Product) => {
    if (step === lastStepNum) {
      // Submit form.
      onSubmit(addedProduct);
    } else {
      // Go to next step.
      setStep(step + 1);
    }
  };

  // Handle clicking Back on form.
  const onBack = () => {
    setStep(step - 1);
    if (step === 1) {
      // User has decided to cancel product creation.
      // Go back to playbook home page.
      onCancel();
    }
  };

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onNext, (err) =>
          console.log("error: ", err)
        )}
        className="space-y-6 rounded-lg border h-fit border-gray-200 bg-white p-6 shadow-md"
      >
        {/* Form Title */}
        <div className="flex flex-col gap-1">
          <h3 className="text-lg font-semibold text-gray-800">
            Product Details
          </h3>
        </div>

        {/* Progress Indicator */}
        <Progress value={(step / lastStepNum) * 100.0} />

        {/* Name Field */}
        {(step === 1 || step === lastStepNum) && (
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel className={formStepClassName}>Name *</FormLabel>
                <FormDescription className="text-sm text-gray-500">
                  The name of the product you are selling.
                </FormDescription>
                <FormControl>
                  <Input
                    className={inputClassName}
                    placeholder="e.g., Userport"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Website Field */}
        {(step === 2 || step === lastStepNum) && (
          <FormField
            control={form.control}
            name="website"
            render={({ field }) => (
              <FormItem>
                <FormLabel className={formStepClassName}>Website *</FormLabel>
                <FormDescription className="text-sm text-gray-500">
                  The website of your product.
                </FormDescription>
                <FormControl>
                  <Input
                    className={inputClassName}
                    placeholder="e.g., https://www.userport.ai"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Description Field */}
        {(step === 3 || step === lastStepNum) && (
          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel className={formStepClassName}>
                  Description *
                </FormLabel>
                <FormDescription className="text-sm text-gray-500">
                  Describe the product, what problem it solves, and its value
                  for the customer.
                </FormDescription>
                <FormDescription className="text-sm text-gray-500">
                  This will be used by AI to match personas better.
                </FormDescription>
                <FormControl>
                  <Textarea
                    className={`${inputClassName} h-32`}
                    placeholder="A sales platform that uses AI to empower BDRs by automating lead research..."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* ICP Field */}
        {(step === 4 || step === lastStepNum) && (
          <FormField
            control={form.control}
            name="icp_description"
            render={({ field }) => (
              <FormItem>
                <FormLabel className={formStepClassName}>ICP *</FormLabel>
                <FormDescription className="text-sm text-gray-500">
                  Describe the Ideal Customer Profile you are selling to.
                </FormDescription>
                <FormControl>
                  <Textarea
                    className={`${inputClassName} h-28`}
                    placeholder="e.g., Sales teams in B2B SaaS companies with 100+ employees and ideally Series B+."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Personas Field */}
        {(step === 5 || step === lastStepNum) && (
          <div className="flex flex-col gap-8">
            <RoleTitleFormField
              form={form}
              fieldPath="persona_role_titles.buyers"
              formStepClassName={formStepClassName}
              inputClassName={inputClassName}
            />

            <RoleTitleFormField
              form={form}
              fieldPath="persona_role_titles.influencers"
              formStepClassName={formStepClassName}
              inputClassName={inputClassName}
            />

            <RoleTitleFormField
              form={form}
              fieldPath="persona_role_titles.end_users"
              formStepClassName={formStepClassName}
              inputClassName={inputClassName}
            />
          </div>
        )}

        {/* Signals Field */}
        {(step === 6 || step === lastStepNum) && (
          <SignalsFormField
            form={form}
            formStepClassName={formStepClassName}
            inputClassName={inputClassName}
          />
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-between gap-4">
          <Button
            type="button"
            variant="outline"
            className="rounded-lg px-6 py-2 text-gray-700 hover:bg-gray-100"
            onClick={onBack}
          >
            {backButtonText}
          </Button>
          <Button
            type="submit"
            className="rounded-lg bg-primary px-6 py-2 text-white shadow-md hover:bg-[rgb(118,102,160)]"
          >
            {nextButtonText}
          </Button>
        </div>
      </form>
    </Form>
  );
};

export default ProductForm;
