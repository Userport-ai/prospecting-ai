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
import { Plus, ExternalLink, Pencil, Trash2 } from "lucide-react";
import { useNavigate } from "react-router";
import { Separator } from "@/components/ui/separator";
import React, { useEffect, useState } from "react";
import { deleteProduct, listProducts, Product } from "@/services/Products";
import { useAuthContext } from "@/auth/AuthProvider";
import { formatDate } from "@/common/utils";
import ScreenLoader from "@/common/ScreenLoader";
import { USERPORT_TENANT_ID } from "@/services/Common";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const DeleteProductAlert: React.FC<{
  name: string;
  handleDelete: () => void;
  children: React.ReactNode;
}> = ({ name, handleDelete, children }) => {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
          <AlertDialogDescription>
            This action will permanently delete the Product {name}. This cannot
            be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleDelete}>
            Yes, Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

// Component Displaying Page Header.
const PageHeader: React.FC<{ handleAddProduct: () => void }> = ({
  handleAddProduct,
}) => {
  return (
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
  );
};

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

// Display Signals that are relevant to given Product.
const Signals: React.FC<{ product: Product }> = ({ product }) => {
  if (!product.playbook_description) {
    return null;
  }
  const allSignals: string[] = product.playbook_description.split("\n");
  return (
    <div className="flex flex-col gap-3">
      {allSignals.map((signal) => (
        <p
          key={signal}
          className="text-sm text-gray-700 border border-gray-400 p-2"
        >
          {signal}
        </p>
      ))}
    </div>
  );
};

interface SingleProductDetailsProps {
  product: Product;
  onDelete: (arg0: string) => void;
  onEdit: (arg0: string) => void;
}

// Component to display a a single product's details.
const SingleProductDetails: React.FC<SingleProductDetailsProps> = ({
  product,
  onDelete,
  onEdit,
}) => {
  return (
    <Card className=" bg-white shadow-lg rounded-none border border-gray-200 overflow-hidden transition-transform hover:shadow-2xl">
      {/* Card Header */}
      <CardHeader className="p-4 bg-gradient-to-r from-[rgb(135,120,169)] to-[rgb(115,99,152)] text-white flex flex-row justify-between items-end">
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
        <div className="flex">
          <Pencil
            className="pr-4 size-8 hover:cursor-pointer hover:text-yellow-300"
            onClick={() => onEdit(product.id!)}
          />
          <DeleteProductAlert
            name={product.name}
            handleDelete={() => onDelete(product.id!)}
          >
            <Trash2 className="pr-4 size-8 hover:cursor-pointer hover:text-yellow-300" />
          </DeleteProductAlert>
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

        {/* Signals */}
        <div>
          <h3 className="text-sm font-semibold text-gray-600 mb-2">Signals</h3>
          <Signals product={product} />
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

// Display when there are no products found on the server.
const ZeroStateDisplay = () => {
  return (
    <div className="flex flex-col mt-20">
      <Card className="max-w-md mx-auto bg-white shadow-xl border border-gray-200 rounded-none">
        <CardHeader className="flex flex-row justify-center items-center bg-[rgb(136,109,195)] p-4">
          <CardTitle className="text-base text-gray-50 tracking-wide">
            Ready to Get Started?
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <p className="text-gray-600 text-base leading-relaxed text-center">
            You haven’t added any products yet. Click the button above to add
            your first product.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

// Component to display all products.
const AllProducts: React.FC<{
  products: Product[];
  onProductDeleted: (arg0: string) => void;
}> = ({ products, onProductDeleted }) => {
  const authContext = useAuthContext();
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  if (products.length === 0) {
    return <ZeroStateDisplay />;
  }

  // Handler when user wants to edit a product.
  const onEdit = (id: string) => {
    console.log("going to edit: ", id);
  };

  // Handler when user wants to delete a product.
  const onDelete = async (id: string) => {
    try {
      if (authContext.userContext?.tenant.id === USERPORT_TENANT_ID) {
        return;
      }
      setLoading(true);
      await deleteProduct(authContext, id);
      onProductDeleted(id);
    } catch (error: any) {
      setError(new Error(`Failed to delete product: ${error.message}`));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="mt-20">
        <ScreenLoader />
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {error && (
        <p className="text-destructive font-medium mt-2">{error.message}</p>
      )}
      <div className="flex flex-col gap-16 mt-10">
        {products.map((product) => (
          <SingleProductDetails
            key={product.id}
            product={product}
            onDelete={onDelete}
            onEdit={onEdit}
          />
        ))}
      </div>
    </div>
  );
};

export default function ProductsPage() {
  const authContext = useAuthContext();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    listProducts(authContext)
      .then((products) => setProducts(products))
      .catch((error) =>
        setError(new Error(`Failed to fetch Products: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext]);

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    return (
      <div className="w-10/12 flex justify-center mt-10 bg-red-100 p-4 rounded-md shadow-md">
        <p className="text-destructive text-lg font-medium">{error.message}</p>
      </div>
    );
  }

  // Handle Add Product click by user.
  const handleAddProduct = () => {
    if (authContext.userContext?.tenant.id === USERPORT_TENANT_ID) {
      return;
    }
    navigate("/playbook/add-product"); // Adjust route to the product creation page.
  };

  // Handle Product Deleted.
  const handleProductDeleted = (id: string) => {
    setProducts(products.filter((product, _) => product.id !== id));
  };

  // Display existing products.
  return (
    <div className="w-11/12 flex flex-col">
      <PageHeader handleAddProduct={handleAddProduct} />
      <Separator />
      <AllProducts
        products={products}
        onProductDeleted={handleProductDeleted}
      />
    </div>
  );
}
