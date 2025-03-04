import ProductForm from "./ProductForm";
import { useEffect, useState } from "react";
import { getProduct, Product, updateProduct } from "@/services/Products";
import { useNavigate, useParams } from "react-router";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";

const EditProduct = () => {
  const authContext = useAuthContext();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const navigate = useNavigate();
  // Product ID must exist in this route.
  const { id } = useParams<{ id?: string }>();
  const productId: string = id!;

  useEffect(() => {
    setLoading(true);
    getProduct(authContext, productId)
      .then((product) => setProduct(product))
      .catch((error) =>
        setError(new Error(`Failed to fetch Product to edit: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext, id]);

  if (loading) {
    return <ScreenLoader />;
  }

  // Handle user saving product.
  const onSave = async (savedProduct: Product) => {
    try {
      await updateProduct(authContext, productId, savedProduct);
      setError(null);
      navigate("/products");
    } catch (error: any) {
      setError(new Error(`Failed to Edit product: ${error.message}`));
    }
  };

  // Haadle user canceling edit.
  const onCancel = () => {
    navigate("/products");
  };

  return (
    <div className="mt-10 flex flex-col gap-4 w-[40rem]">
      {error && <p className="text-sm text-red-500">{error.message}</p>}
      <ProductForm
        product={product!}
        operation="edit"
        onSubmit={onSave}
        onCancel={onCancel}
      />
    </div>
  );
};

export default EditProduct;
