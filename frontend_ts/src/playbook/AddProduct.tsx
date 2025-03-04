import { useState } from "react";
import { useNavigate } from "react-router";
import { addProduct, Product } from "@/services/Products";
import { useAuthContext } from "@/auth/AuthProvider";
import ProductForm from "./ProductForm";

// Handle Product creation sequence.
function AddProduct() {
  const authContext = useAuthContext();
  // Product Details JSON.
  const product: Product = {
    name: "",
    description: "",
    website: "",
    icp_description: "",
    persona_role_titles: {
      buyers: [],
      influencers: [],
      end_users: [],
    },
    playbook_description: "",
  };

  const [error, setError] = useState<Error | null>(null);
  const navigate = useNavigate();

  // Handle user submitting the form
  const handleSubmit = async (addedProduct: Product) => {
    try {
      await addProduct(authContext, addedProduct);
      setError(null);
      navigate("/products");
    } catch (error: any) {
      setError(new Error(`Failed to Add product: ${error.message}`));
    }
  };

  // Handle canceling adding the product.
  function handleCancel() {
    navigate("/products");
  }

  return (
    <div className="mt-10 flex flex-col gap-4 w-[40rem]">
      {error && <p className="text-sm text-red-500">{error.message}</p>}
      <ProductForm
        product={product}
        operation="create"
        onSubmit={handleSubmit}
        onCancel={handleCancel}
      />
    </div>
  );
}

export default AddProduct;
