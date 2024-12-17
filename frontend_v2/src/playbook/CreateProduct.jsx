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
  // 1. Define your form.
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

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onNext)} className="space-y-8">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormDescription>
                The name of the product you are selling.
              </FormDescription>
              <FormControl>
                <Input
                  className="border-border rounded-lg placeholder:text-gray-400"
                  placeholder="Userport"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormDescription>
                Describe the product, what problem it solves and what value it
                adds for the customer.
              </FormDescription>
              <FormControl>
                <Textarea
                  className="h-40 border-border rounded-lg placeholder:text-gray-400"
                  placeholder="Sales platform that uses AI to empower SDRs by conducting account and lead research, delivering actionable insights, and crafting tailored messaging—all perfectly aligned with the the customer's sales playbook."
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {step === 2 && (
          <FormField
            control={form.control}
            name="icp"
            render={({ field }) => (
              <FormItem>
                <FormLabel>ICP</FormLabel>
                <FormDescription>
                  Describe the Ideal Customer Profile you are selling to.
                </FormDescription>
                <FormControl>
                  <Textarea
                    className="h-40 border-border rounded-lg placeholder:text-gray-400"
                    placeholder="We are selling to Director of Sales in Series B+ companies with employee counts greater than 100."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}
        {step === 2 && (
          <FormField
            control={form.control}
            name="personas"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Personas</FormLabel>
                <FormDescription>
                  Describe the personas within the ICPs who you will need to
                  target with your outreach efforts.
                </FormDescription>
                <FormControl>
                  <Textarea
                    className="h-28 border-border rounded-lg placeholder:text-gray-400"
                    placeholder="Director of Sales, VP of Sales, Head of Sales"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}
        {step === 2 && (
          <FormField
            control={form.control}
            name="keywords"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Keywords</FormLabel>
                <FormDescription>
                  Describe any keywords that are associated with your product's
                  domain.
                </FormDescription>
                <FormControl>
                  <Textarea
                    className="h-20 border-border rounded-lg placeholder:text-gray-400"
                    placeholder="Sales Prospecting, Outbound, Lead Generation, Cold Outreach"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}
        <div className="flex flex-row justify-between">
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">{nextButtonText}</Button>
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
      <div className="border border-border rounded-lg shadow h-fit p-6 mt-20 bg-card">
        {<CreateProduct />}
      </div>
    </div>
  );
}

export default Playbook;
