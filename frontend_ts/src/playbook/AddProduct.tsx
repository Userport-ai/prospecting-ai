import React, { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ControllerRenderProps, useForm } from "react-hook-form";
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
import { WandSparkles } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useNavigate } from "react-router";
import { addProduct, Product } from "@/services/Products";
import { useAuthContext } from "@/auth/AuthProvider";

const GenAIButton: React.FC<{ onClick: () => void }> = ({ onClick }) => {
  return (
    <div>
      <Button
        type="button"
        className="w-fit rounded-xl bg-transparent border"
        onClick={onClick}
      >
        <WandSparkles className="text-purple-400" />
        <p className="text-purple-400">AI</p>
      </Button>
    </div>
  );
};

interface ProductFormProps {
  product: Product;
  step: number;
  onNext: (addedProduct: Product) => void; // Type for the onClick callback
  onCancel: () => void;
}

const ProductForm: React.FC<ProductFormProps> = ({
  product,
  step,
  onNext,
  onCancel,
}) => {
  const formSchema = z.object({
    name: z.string().min(1, "Name is required"),
    description: z.string().min(step > 1 ? 1 : 0, "Description is required"),
    website:
      step > 2
        ? z.string().startsWith("https://", "Website must start with https://")
        : z.string(),
    icp_description: z.string().min(step > 3 ? 1 : 0, "ICP is required"),
    persona_role_titles: z.object({
      buyers: z
        .array(z.string())
        .min(step > 4 ? 1 : 0, "Buyers input is required"),
      influencers: z
        .array(z.string())
        .min(step > 4 ? 1 : 0, "Influencers input is required"),
      end_users: z
        .array(z.string())
        .min(step > 4 ? 1 : 0, "End Users input is required"),
    }),
  });
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: product,
  });

  const nextButtonText = step === 6 ? "Submit" : "Next";
  const backButtonText = step === 1 || step === 6 ? "Cancel" : "Back";

  // Handle user request to generate given field (name, value) using AI.
  function generateUsingAI(field: ControllerRenderProps<Product>) {
    // TODO: Fetch from server.
    console.log("Generate value for field using AI: ", field);
  }

  // Input and textarea base styles
  const inputClassName =
    "w-full rounded-lg border border-gray-300 bg-white py-2 px-4 placeholder-gray-400 focus:border-primary focus:ring-2 focus:ring-primary shadow-sm";

  // AI generation
  const aiGenContainerClassName = "flex flex-row justify-between items-start";

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onNext, (err) =>
          console.log("error: ", err)
        )}
        className="space-y-8 rounded-lg border h-fit border-gray-200 bg-white p-6 shadow-md"
      >
        {/* Progress Indicator */}
        <Progress value={(step / 6.0) * 100.0} />

        {/* Form Title */}
        <h2 className="text-xl font-semibold text-gray-800">Product Details</h2>
        <p className="text-sm text-gray-500">
          Fill out the form below to describe your product. Fields marked with
          an asterisk (*) are required.
        </p>

        {/* Name Field */}
        {(step === 1 || step === 6) && (
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-gray-700">Name *</FormLabel>
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

        {/* Description Field */}
        {(step === 2 || step === 6) && (
          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-gray-700">Description *</FormLabel>
                <FormDescription className="text-sm text-gray-500">
                  Describe the product, what problem it solves, and its value
                  for the customer.
                </FormDescription>
                <FormControl>
                  <Textarea
                    className={`${inputClassName} h-32`}
                    placeholder="A sales platform that uses AI to empower SDRs by conducting account and lead research..."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Website Field */}
        {(step === 3 || step === 6) && (
          <FormField
            control={form.control}
            name="website"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-gray-700">Website *</FormLabel>
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

        {/* ICP Field */}
        {(step === 4 || step === 6) && (
          <FormField
            control={form.control}
            name="icp_description"
            render={({ field }) => (
              <FormItem>
                <div className={aiGenContainerClassName}>
                  <div>
                    <FormLabel className="text-gray-700">ICP *</FormLabel>
                    <FormDescription className="text-sm text-gray-500">
                      Describe the Ideal Customer Profile you are selling to.
                    </FormDescription>
                  </div>
                  <GenAIButton onClick={() => generateUsingAI(field)} />
                </div>
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
        {(step === 5 || step === 6) && (
          <div className="flex flex-col gap-10">
            <FormField
              control={form.control}
              name="persona_role_titles.buyers"
              render={({ field }) => (
                <FormItem>
                  <div className={aiGenContainerClassName}>
                    <div>
                      <FormLabel className="text-gray-700">Buyers *</FormLabel>
                      <FormDescription className="text-sm text-gray-500">
                        Provide role titles and use commas to separate multiple
                        personas.
                      </FormDescription>
                    </div>
                    <GenAIButton onClick={() => generateUsingAI(field)} />
                  </div>
                  <FormControl>
                    <Input
                      className={`${inputClassName}`}
                      placeholder="e.g., Director of Sales, VP of Sales, Head of Sales"
                      onBlur={(e) => {
                        const inputValue = e.target.value;
                        // Convert the string to an array of strings.
                        const arrayValue = inputValue
                          .split(",")
                          .map((item) => item.trim())
                          .filter(Boolean); // Remove empty strings
                        field.onChange(arrayValue); // Pass the array to the form state
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="persona_role_titles.influencers"
              render={({ field }) => (
                <FormItem>
                  <div className={aiGenContainerClassName}>
                    <div>
                      <FormLabel className="text-gray-700">
                        Influencers *
                      </FormLabel>
                      <FormDescription className="text-sm text-gray-500">
                        Provide role titles and use commas to separate multiple
                        personas.
                      </FormDescription>
                    </div>
                    <GenAIButton onClick={() => generateUsingAI(field)} />
                  </div>
                  <FormControl>
                    <Input
                      className={`${inputClassName}`}
                      placeholder="e.g., Sales Development Manager, Business Development Manager"
                      onBlur={(e) => {
                        const inputValue = e.target.value;
                        // Convert the string to an array of strings.
                        const arrayValue = inputValue
                          .split(",")
                          .map((item) => item.trim())
                          .filter(Boolean); // Remove empty strings
                        field.onChange(arrayValue); // Pass the array to the form state
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="persona_role_titles.end_users"
              render={({ field }) => (
                <FormItem>
                  <div className={aiGenContainerClassName}>
                    <div>
                      <FormLabel className="text-gray-700">
                        End Users *
                      </FormLabel>
                      <FormDescription className="text-sm text-gray-500">
                        Provide role titles and use commas to separate multiple
                        personas.
                      </FormDescription>
                    </div>
                    <GenAIButton onClick={() => generateUsingAI(field)} />
                  </div>
                  <FormControl>
                    <Input
                      className={`${inputClassName}`}
                      placeholder="e.g., Sales Development Representatives, Account Executives"
                      onBlur={(e) => {
                        const inputValue = e.target.value;
                        // Convert the string to an array of strings.
                        const arrayValue = inputValue
                          .split(",")
                          .map((item) => item.trim())
                          .filter(Boolean); // Remove empty strings
                        field.onChange(arrayValue); // Pass the array to the form state
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-between gap-4">
          <Button
            type="button"
            variant="outline"
            className="rounded-lg px-6 py-2 text-gray-700 hover:bg-gray-100"
            onClick={onCancel}
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

// Handle Product creation sequence.
function AddProduct() {
  const authContext = useAuthContext();
  // Product Details JSON.
  const [product, setProduct] = useState<Product>({
    name: "",
    description: "",
    website: "",
    icp_description: "",
    persona_role_titles: {
      buyers: [],
      influencers: [],
      end_users: [],
    },
  });
  // State to manage the current step of the form
  const [step, setStep] = useState(1);
  const [error, setError] = useState<Error | null>(null);
  const navigate = useNavigate();

  // Handle user clicking next on form.
  const handleNext = async (addedProduct: Product) => {
    setProduct(addedProduct);
    if (step === 6) {
      // Submit form.
      try {
        await addProduct(authContext, addedProduct);
        setError(null);
        navigate("/playbook");
      } catch (error: any) {
        setError(new Error(`Failed to Add product: ${error.message}`));
      }
    } else {
      // Go to next step.
      setStep(step + 1);
    }
  };

  // Handle canceling creating the product.
  function handleCancel() {
    setStep(step - 1);
    if (step === 1 || step === 6) {
      // User has decided to cancel product creation.
      // Go back to playbook home page.
      navigate("/playbook");
    }
  }

  return (
    <div className="mt-10 flex flex-col gap-4">
      {error && <p className="text-sm text-red-500">{error.message}</p>}
      <ProductForm
        product={product}
        step={step}
        onNext={handleNext}
        onCancel={handleCancel}
      />
    </div>
  );
}

export default AddProduct;
