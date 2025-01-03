import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, ExternalLink, Pencil } from "lucide-react";
import { useNavigate } from "react-router";
import { Separator } from "@/components/ui/separator";

// Should be a subset of 'Products' Model in the backend.
interface ProductDetails {
  id: string;
  name: string;
  description: string;
  website: string,
  icp_description: string;
  persona_role_titles: {
    roles: string[];
  }
  created_at: string; // ISO 8601 date string
  updated_at: string; // ISO 8601 date string
}

const ProductDetailsDisplay: React.FC<{product: ProductDetails}> = ({ product }) => {
  return (
    <Card className=" bg-white shadow-lg rounded-none border border-gray-200 overflow-hidden transition-transform hover:shadow-2xl">
      {/* Card Header */}
      <CardHeader className="p-4 bg-gradient-to-r from-[rgb(135,120,169)] to-[rgb(115,99,152)] text-white flex flex-row justify-between items-center">
        <div>
          <CardTitle className="text-xl font-bold tracking-wide">
            {product.name}
          </CardTitle>
          <CardDescription className="text-sm mt-1">
            <a
              href={product.website}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-white hover:text-white hover:underline"
            >
              {product.website} <ExternalLink size={16} />
            </a>
          </CardDescription>
        </div>
        <div>
          <Pencil
            className="pr-4 size-10 hover:cursor-pointer"
            onClick={() => console.log("edit clicked")}
          />
        </div>
      </CardHeader>

      {/* Card Content */}
      <CardContent className="p-6 space-y-6">
        {/* Description */}
        <div>
          <h3 className="text-sm font-semibold text-gray-600 mb-1">
            Description
          </h3>
          <p className="text-gray-700 text-base leading-relaxed">
            {product.description}
          </p>
        </div>

        {/* ICP */}
        <div>
          <h3 className="text-sm font-semibold text-gray-600 mb-1">ICP</h3>
          <p className="text-gray-700 text-base">{product.icp_description}</p>
        </div>

        {/* Personas */}
        <div>
          <h3 className="text-sm font-semibold text-gray-600 mb-1">Personas</h3>
          <div className="flex flex-wrap gap-2">
            {product.persona_role_titles.roles.map((role, index) => (
              <Badge
                key={index}
                variant="outline"
                className="bg-gray-100 text-gray-800 font-medium px-3 py-1 rounded-full shadow-sm"
              >
                {role}
              </Badge>
            ))}
          </div>
        </div>
      </CardContent>

      {/* Card Footer */}
      <CardFooter className="p-4 bg-gray-50 border-t border-gray-200 flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
        {/* Creation & Last Updated */}
        <div className="text-sm text-gray-500 space-y-1">
          <p>
            <span className="font-semibold">Created on:</span>{" "}
            <span className="text-gray-800">{product.created_at}</span>
          </p>
          <p>
            <span className="font-semibold">Last Updated:</span>{" "}
            <span className="text-gray-800">{product.updated_at}</span>
          </p>
        </div>
      </CardFooter>
    </Card>
  );
}

export default function ProductsPage() {
  // Mock data for demonstration purposes.
  // Replace with products fetched from API call.
  const products: Readonly<ProductDetails[]> = [
    {
      id: "1",
      name: "Userport AI",
      description:
        "An AI-powered platform to supercharge your sales by conducting account and lead research, delivering actionable insights, and crafting tailored messaging.",
      website: "https://www.userport.ai",
      icp_description: "Sales teams at Series B+ companies",
      persona_role_titles: {roles: ["VP of Sales", "Director of Sales", "Account Executive"]},
      created_at: "2023-06-01",
      updated_at: "2024-12-10",
    },
    // Add more products...
  ];
  // const products = [];

  const navigate = useNavigate();

  const handleAddProduct = () => {
    navigate("/playbook/add-product"); // Adjust route to the product creation page.
  };

  // Display existing products.
  return (
    <div className="w-11/12 flex flex-col">
      <div className="flex justify-between items-end mb-4">
        <h1 className="text-2xl font-semibold text-gray-600 tracking-tight">
          Your Products
        </h1>
        <Button
          variant={"default"}
          className="bg-primary text-primary-foreground hover:bg-primary shadow-md px-4 py-2 transition-all duration-300"
          onClick={handleAddProduct}
        >
          <Plus className="mr-2" size={16} />
          Add Product
        </Button>
      </div>
      <Separator />
      {products.length === 0 && (
        <div className="flex flex-col mt-20">
          <Card className="max-w-md mx-auto bg-white shadow-xl border border-gray-200 rounded-none">
            <CardHeader className="flex flex-row justify-center items-center bg-[rgb(136,109,195)] p-4">
              <CardTitle className="text-base text-gray-50 tracking-wide">
                Ready to Get Started?
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              <p className="text-gray-600 text-base leading-relaxed text-center">
                You haven’t added any products yet. Click the button above to
                add your first product.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
      <div className="flex flex-col gap-6 mt-10">
        {products.map((product) => (
          <ProductDetailsDisplay key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}
