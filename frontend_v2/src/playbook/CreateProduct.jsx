import React, { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
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

function ProductForm({ productDetails, step, onNext, onCancel }) {
  const formSchema = z.object({
    name: z.string().min(1),
    description: z.string().min(2),
    icp: z.string(),
    personas: z.string(),
    keywords: z.string(),
  });

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: productDetails,
  });

  const nextButtonText = step > 1 ? "Submit" : "Next";

  // Input and textarea base styles
  const inputClassName =
    "w-full rounded-lg border border-gray-300 bg-white py-2 px-4 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-400 shadow-sm";

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onNext)}
        className="space-y-8 rounded-lg border border-gray-200 bg-white p-6 shadow-md"
      >
        {/* Form Title */}
        <h2 className="text-xl font-semibold text-gray-800">Product Details</h2>
        <p className="text-sm text-gray-500">
          Fill out the form below to describe your product. Fields marked with
          an asterisk (*) are required.
        </p>

        {/* Name Field */}
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

        {/* Description Field */}
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel className="text-gray-700">Description *</FormLabel>
              <FormDescription className="text-sm text-gray-500">
                Describe the product, what problem it solves, and its value for
                the customer.
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

        {/* Step 2 Fields */}
        {step === 2 && (
          <>
            {/* ICP Field */}
            <FormField
              control={form.control}
              name="icp"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-gray-700">ICP</FormLabel>
                  <FormDescription className="text-sm text-gray-500">
                    Describe the Ideal Customer Profile you are selling to.
                  </FormDescription>
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

            {/* Personas Field */}
            <FormField
              control={form.control}
              name="personas"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-gray-700">Personas</FormLabel>
                  <FormDescription className="text-sm text-gray-500">
                    Describe the personas within the ICP you will target with
                    your outreach efforts.
                  </FormDescription>
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

            {/* Keywords Field */}
            <FormField
              control={form.control}
              name="keywords"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-gray-700">Keywords</FormLabel>
                  <FormDescription className="text-sm text-gray-500">
                    List any keywords associated with your product's domain.
                  </FormDescription>
                  <FormControl>
                    <Textarea
                      className={`${inputClassName} h-20`}
                      placeholder="e.g., Sales Prospecting, Outbound, Lead Generation"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-4">
          <Button
            type="button"
            variant="outline"
            className="rounded-lg px-6 py-2 text-gray-700 hover:bg-gray-100"
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            className="rounded-lg bg-indigo-600 px-6 py-2 text-white shadow-md hover:bg-indigo-700"
          >
            {nextButtonText}
          </Button>
        </div>
      </form>
    </Form>
  );
}

// Handle Product creation sequence.
function CreateProduct() {
  // Product Details JSON.
  const [productDetails, setProductDetails] = useState({
    name: "",
    description: "",
    icp: "",
    personas: "",
    keywords: "",
  });

  // State to manage the current step of the form
  const [step, setStep] = useState(1);

  // Handle user clicking next on form.
  function handleNext(newProductDetails) {
    console.log("got new product details: ", newProductDetails);
    setProductDetails(newProductDetails);
    setStep(step + 1);
    if (step === 1) {
      // TODO: We need to fetch the recommended ICP, Personas and Keywords from API fetch.
    } else {
      // TODO: Submit product details to backend.
    }
  }

  // Handle canceling creating the product.
  function handleCancel() {
    // User has decided to cancel product creation.
    // TODO: callback.
    setStep(step - 1);
  }

  return (
    <ProductForm
      productDetails={productDetails}
      step={step}
      onNext={handleNext}
      onCancel={handleCancel}
    />
  );
}

function Playbook() {
  return (
    <div className="w-full flex justify-center items-start">
      <div className="mt-20 mb-10">{<CreateProduct />}</div>
    </div>
  );
}

export default Playbook;
