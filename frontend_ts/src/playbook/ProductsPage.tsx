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
import { useEffect, useState } from "react";
import { listProducts, Product } from "@/services/Products";
import { useAuthContext } from "@/auth/AuthProvider";
import { formatDate } from "@/common/utils";
import ScreenLoader from "@/common/ScreenLoader";

// Returns component to display Personas.
const PersonasDisplay: React.FC<{ product: Product }> = ({ product }) => {
  const buyersComp = product.persona_role_titles.buyers && (
    <div className="flex items-center gap-2">
      <p className="text-gray-600 text-sm font-medium">Buyers:</p>
      <div className="flex flex-wrap gap-2">
        {product.persona_role_titles.buyers.map((role, index) => (
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
  );

  const influencersComp = product.persona_role_titles.influencers && (
    <div className="flex items-center gap-2">
      <p className="text-gray-600 text-sm font-medium">Influencers:</p>
      <div className="flex flex-wrap gap-2">
        {product.persona_role_titles.influencers.map((role, index) => (
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
  );

  const endUsersComp = product.persona_role_titles.end_users && (
    <div className="flex items-center gap-2">
      <p className="text-gray-600 text-sm font-medium">End Users:</p>
      <div className="flex flex-wrap gap-2">
        {product.persona_role_titles.end_users.map((role, index) => (
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
  );

  return (
    <div className="flex flex-col gap-4">
      {buyersComp}
      {influencersComp}
      {endUsersComp}
    </div>
  );
};

const ProductDetailsDisplay: React.FC<{ product: Product }> = ({ product }) => {
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
          <h3 className="text-sm font-semibold text-gray-600 mb-2">Personas</h3>
          <PersonasDisplay product={product} />
        </div>
      </CardContent>

      {/* Card Footer */}
      <CardFooter className="p-4 bg-gray-50 border-t border-gray-200 flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
        {/* Creation & Last Updated */}
        <div className="text-sm text-gray-500 space-y-1">
          <p>
            <span className="font-semibold">Created on:</span>{" "}
            <span className="text-gray-800">
              {product.created_at ? formatDate(product.created_at) : "Unknown"}
            </span>
          </p>
          <p>
            <span className="font-semibold">Last Updated:</span>{" "}
            <span className="text-gray-800">
              {product.updated_at ? formatDate(product.updated_at) : "Unknown"}
            </span>
          </p>
        </div>
      </CardFooter>
    </Card>
  );
};

export default function ProductsPage() {
  const { firebaseUser, userContext } = useAuthContext();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    listProducts(firebaseUser, userContext)
      .then((products) => setProducts(products))
      .catch((error) =>
        setError(new Error(`Failed to fetch Products: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [firebaseUser, userContext]);

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    throw error;
  }

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
      <div className="flex flex-col gap-16 mt-10">
        {products.map((product) => (
          <ProductDetailsDisplay key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}
