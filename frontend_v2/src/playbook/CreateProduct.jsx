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

function ChatGPTPlaybook() {
  // State to hold the list of products
  const [products, setProducts] = useState([]);
  // State to manage the current step of the form
  const [step, setStep] = useState(1);
  // State to manage the form inputs
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    icp: "",
    personas: "",
  });

  // Handler to update form inputs
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  // Handler to navigate steps
  const nextStep = () => setStep((prev) => Math.min(prev + 1, 4));
  const prevStep = () => setStep((prev) => Math.max(prev - 1, 1));

  // Handler to add a new product
  const handleAddProduct = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    const newProduct = {
      id: Date.now(), // Unique ID for the product
      ...formData,
    };

    setProducts([...products, newProduct]);
    setFormData({ name: "", description: "", icp: "", personas: "" }); // Reset form
    setStep(1); // Reset to first step
  };

  // JSX for the Playbook component
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Playbook: Create a Product</h1>

      {/* Multi-step Form to create a product */}
      <form
        onSubmit={handleAddProduct}
        className="bg-white shadow-md rounded px-8 pt-6 pb-8 mb-4"
      >
        {step === 1 && (
          <div className="mb-4">
            <label
              htmlFor="name"
              className="block text-gray-700 text-sm font-bold mb-2"
            >
              Product Name
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              placeholder="Enter product name"
            />
          </div>
        )}

        {step === 2 && (
          <div className="mb-4">
            <label
              htmlFor="description"
              className="block text-gray-700 text-sm font-bold mb-2"
            >
              Product Description
            </label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              placeholder="Enter product description"
            />
          </div>
        )}

        {step === 3 && (
          <div className="mb-4">
            <label
              htmlFor="icp"
              className="block text-gray-700 text-sm font-bold mb-2"
            >
              Ideal Customer Profile (ICP)
            </label>
            <input
              type="text"
              id="icp"
              name="icp"
              value={formData.icp}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              placeholder="Enter ICP"
            />
          </div>
        )}

        {step === 4 && (
          <div className="mb-4">
            <label
              htmlFor="personas"
              className="block text-gray-700 text-sm font-bold mb-2"
            >
              Personas
            </label>
            <input
              type="text"
              id="personas"
              name="personas"
              value={formData.personas}
              onChange={handleChange}
              className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
              placeholder="Enter personas"
            />
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex justify-between">
          {step > 1 && (
            <button
              type="button"
              onClick={prevStep}
              className="bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
              Previous
            </button>
          )}

          {step < 4 ? (
            <button
              type="button"
              onClick={nextStep}
              className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
              Next
            </button>
          ) : (
            <button
              type="submit"
              className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
              Submit
            </button>
          )}
        </div>
      </form>

      {/* Displaying the list of products */}
      <div>
        <h2 className="text-xl font-bold mb-4">Created Products</h2>
        {products.length === 0 ? (
          <p className="text-gray-500">No products created yet.</p>
        ) : (
          <ul className="list-disc pl-5">
            {products.map((product) => (
              <li key={product.id} className="text-gray-700 mb-2">
                <strong>{product.name}</strong>: {product.description}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

const formSchema = z.object({
  name: z.string().min(2).max(50),
  description: z.string().min(10),
});

function CreateProduct() {
  // 1. Define your form.
  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  // 2. Define a submit handler.
  function onSubmit(values) {
    // Do something with the form values.
    console.log(values);
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
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
                  className="border-border rounded-lg"
                  placeholder=""
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
                  className="border-border rounded-lg"
                  placeholder=""
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Submit</Button>
      </form>
    </Form>
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
