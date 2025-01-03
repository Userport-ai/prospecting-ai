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


interface ProductDetails {
  name: string;
  description: string;
  website: string;
  icp: string;
  personas: string;
} 

const GenAIButton: React.FC<{onClick: () => void}> =  ({ onClick }) => {
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
}

interface ProductFormProps {
  productDetails: ProductDetails;
  step: number;
  onNext: (details: ProductDetails) => void; // Type for the onClick callback
  onCancel: () => void;
}

const  ProductForm: React.FC<ProductFormProps> = ({ productDetails, step, onNext, onCancel }) => {
  const formSchema = z.object({
    name: z.string().min(1, "Name is required"),
    description: z.string().min(step > 1 ? 1 : 0, "Description is required"),
    website: z.string().min(step > 2? 1: 0).startsWith("https://", "Website is required"),
    icp: z.string().min(step > 3 ? 1: 0, "ICP is required"),
    personas: z.string().min(step > 4 ? 1: 0, "Personas are required"),
  });
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: productDetails,
  });

  const nextButtonText = step === 6 ? "Submit" : "Next";
  const backButtonText = step === 1 || step === 6 ? "Cancel" : "Back";

  // Handle user request to generate given field (name, value) using AI.
  function generateUsingAI(field: ControllerRenderProps<ProductDetails>) {
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
        onSubmit={form.handleSubmit(onNext)}
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
            name="icp"
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
                    placeholder="e.g., Director of Sales in Series B+ companies with 100+ employees."
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
          <FormField
            control={form.control}
            name="personas"
            render={({ field }) => (
              <FormItem>
                <div className={aiGenContainerClassName}>
                  <div>
                    <FormLabel className="text-gray-700">Personas *</FormLabel>
                    <FormDescription className="text-sm text-gray-500">
                      Describe the personas within the ICP you will target with
                      your outreach efforts.
                    </FormDescription>
                  </div>
                  <GenAIButton onClick={() => generateUsingAI(field)} />
                </div>
                <FormControl>
                  <Textarea
                    className={`${inputClassName} h-24`}
                    placeholder="e.g., Director of Sales, VP of Sales, Head of Sales"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
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
}

// Handle Product creation sequence.
function AddProduct() {
  // Product Details JSON.
  const [productDetails, setProductDetails] = useState<ProductDetails>({
    name: "",
    description: "",
    website: "",
    icp: "",
    personas: "",
  });
  const navigate = useNavigate();

  // State to manage the current step of the form
  const [step, setStep] = useState(1);

  // Handle user clicking next on form.
  function handleNext(newProductDetails: ProductDetails) {
    console.log("got updated product details: ", newProductDetails);
    setProductDetails(newProductDetails);
    setStep(step + 1);
    if (step === 6) {
      // TODO: Submit product details to backend.
      navigate("/playbook");
    }
  }

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
    <div className="mt-10">
      <ProductForm
        productDetails={productDetails}
        step={step}
        onNext={handleNext}
        onCancel={handleCancel}
      />
    </div>
  );
}

export default AddProduct;
