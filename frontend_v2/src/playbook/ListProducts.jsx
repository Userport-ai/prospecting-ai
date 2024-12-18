import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router";

function ListProducts() {
  // Mock data for demonstration purposes.
  // Replace with products fetched from API call.
  const products = [];

  const navigate = useNavigate();

  const handleAddProduct = () => {
    navigate("/playbook/add-product"); // Adjust route to the product creation page.
  };

  if (products.length === 0) {
    // Case 1: No products exist.
    return (
      <Card className="max-w-md mx-auto bg-white shadow-xl border border-gray-200 rounded-none">
        <CardHeader className="flex flex-row justify-center items-center p-2 bg-[rgb(143,118,197)]">
          <CardTitle className="text-base text-gray-50 tracking-wide">
            Ready to Get Started?
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <p className="text-gray-600 text-base leading-relaxed text-center">
            You haven’t added details of any products yet. Click below to add
            your first product and embark on your journey to successful
            outreach!
          </p>
        </CardContent>
        <CardFooter className="flex justify-center p-5">
          <Button
            variant="primary"
            className="w-full py-2 bg-primary text-primary-foreground hover:bg-[rgb(85,70,120)] focus:ring-2 focus:ring-[rgb(101,85,143)] focus:outline-none transition-all duration-300"
            onClick={handleAddProduct}
          >
            Add Product
          </Button>
        </CardFooter>
      </Card>
    );
  }

  // Case 2: Existing products exist.
  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold text-gray-800">Your Products</h1>
        <Button variant="primary" onClick={handleAddProduct}>
          <Plus className="mr-2" size={16} />
          Add Product
        </Button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {products.map((product) => (
          <Card key={product.id} className="bg-white shadow-lg rounded-lg">
            <CardHeader className="p-4 border-b">
              <CardTitle className="text-lg font-medium text-gray-800">
                {product.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <p className="text-sm text-gray-600">{product.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default ListProducts;
