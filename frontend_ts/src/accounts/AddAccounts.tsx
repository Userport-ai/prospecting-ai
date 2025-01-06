import React, { ChangeEvent, DragEvent, useState } from "react";
import { Plus, Upload, FileIcon, XCircle } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { DialogProps } from "@radix-ui/react-dialog";
import { parse, ParseResult } from "papaparse";
import { Product } from "@/services/Products";
import { Account, createAccounts } from "@/services/Accounts";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";

// Component that lets the user select a product.
const ProductSelection: React.FC<{
  // field: ControllerRenderProps<any>;
  defaultValue: string | undefined;
  onValueChange: (arg0: string) => void;
  products: Product[];
}> = ({ defaultValue, onValueChange, products }) => {
  return (
    <Select onValueChange={onValueChange} defaultValue={defaultValue}>
      <SelectTrigger className="border-gray-300">
        <SelectValue placeholder="Select a Product" />
      </SelectTrigger>
      <SelectContent>
        {products.map((product) => (
          <SelectItem key={product.id} value={product.id!}>
            {product.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

// Component to let user upload a file from their computer.
export const FileUpload: React.FC<{
  onFileUpload: (arg0: File | null) => void;
}> = ({ onFileUpload }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // Validates that the uploaded file is a CSV file.
  // If so, the file is sent to the parent.
  const validateUploadedFileAndDispath = (file: File) => {
    if (file.type !== "text/csv") {
      setErrorMessage(`Error! Invalid file type, expected CSV!`);
      return;
    }

    // File is valid CSV.
    setErrorMessage(null);
    setSelectedFile(file);

    // Callback parent.
    onFileUpload(file);
  };

  // Handle when the file is uploaded via Input.
  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) {
      setErrorMessage("Error! No File uploaded!");
      return;
    }
    const file = event.target.files[0];
    validateUploadedFileAndDispath(file);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => {
    setDragging(false);
  };

  // Hande when a file is dragged and dropped to the component.
  const handleFileDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!event.dataTransfer) {
      setErrorMessage("Error! No File was dropped!");
      return;
    }
    const file = event.dataTransfer.files[0];
    validateUploadedFileAndDispath(file);
  };

  // Handle uploaded file removal for user.
  const handleFileRemoval = () => {
    setSelectedFile(null);
    onFileUpload(null);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Display error if any. */}
      {errorMessage && (
        <Label className="text-destructive">{errorMessage}</Label>
      )}
      {/* When no file is not uploaded yet. */}
      {!selectedFile && (
        <div
          className={`border-2 ${
            dragging
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-gray-50"
          } rounded-md p-4 text-center transition-all duration-300`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleFileDrop}
        >
          <Input
            id="file-upload"
            type="file"
            className="hidden"
            onChange={handleFileChange}
          />
          <Label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center gap-2 cursor-pointer text-gray-500 hover:text-gray-700"
          >
            <Upload className="w-6 h-6" />
            <span className="text-sm">{"Drag & Drop or Click to Upload"}</span>
          </Label>
        </div>
      )}

      {/* When file is successfully uploaded. */}
      {selectedFile && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-4 border border-gray-200 bg-gray-50 rounded-md px-4 py-2">
            <FileIcon className="text-gray-600" size={24} />
            <span className="text-sm text-gray-700">{selectedFile.name}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleFileRemoval}
              className="text-purple-700 hover:bg-red-50"
            >
              <XCircle size={18} />
              Remove
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

interface ImportCSVProps {
  products: Product[];
  open: DialogProps["open"];
  onOpenChange: (open: boolean) => void;
  onImported: (createdAccounts: Account[]) => void;
}

// Dialog that enables user to import CSV
const ImportCSV: React.FC<ImportCSVProps> = ({
  products,
  open,
  onOpenChange,
  onImported,
}) => {
  const authContext = useAuthContext();
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // CSV File is uploaded. Will validate contents during submit.
  const handleFileUpload = (file: File | null) => {
    setUploadedFile(file);
    setErrorMessage(null);
  };

  // Calls backend API to enrich the given accounts.
  const enrichAccounts = (accountNames: string[], productId: string) => {
    const accounts = accountNames.map((name) => {
      return {
        name: name,
      };
    });

    setLoading(true);
    createAccounts(authContext, { accounts: accounts, product: productId })
      .then((createdAccounts) => onImported(createdAccounts))
      .catch((error) =>
        setErrorMessage(`Failed to Import Accounts: ${error.message}`)
      )
      .finally(() => setLoading(false));
  };

  // Handle user submitting CSV and production selection.
  const handleSubmit = () => {
    if (!uploadedFile) {
      setErrorMessage("Please upload a file first!");
      return;
    }
    if (!selectedProduct) {
      setErrorMessage("Please select a product!");
      return;
    }
    const reader = new FileReader();

    // Read the file as text
    reader.onload = (event) => {
      const text = event.target?.result as string;

      // Parse the CSV using Papaparse
      parse(text, {
        header: true, // Treat the first row as headers
        skipEmptyLines: true,
        complete: (results: ParseResult<Record<string, any>>) => {
          const data: Record<string, any>[] = results.data;
          // Validate the uploaded CSV.
          if (data.length === 0) {
            setErrorMessage(`Error! File is empty with no data!`);
            return;
          }
          const expectedAccountNameHeader = "Company Name";
          if (!(expectedAccountNameHeader in data[0])) {
            setErrorMessage(
              `"Company Name" column does not exist or it's not in the first Row of the CSV. Please reupload the file with the right Column Name!`
            );
            return;
          }
          if (data.length > 20) {
            setErrorMessage(
              `Error! More than 20 accounts uploaded, please retry with fewer accounts!`
            );
            return;
          }
          // Gather all Account Names.
          const accountNames: string[] = data.map(
            (row) => row[expectedAccountNameHeader] as string
          );

          enrichAccounts(accountNames, selectedProduct);
        },
        error: (error: any) => {
          setErrorMessage(`Failed to process file: ${error.message}`);
        },
      });
    };

    reader.onerror = () => {
      setErrorMessage("Error reading the file. Please try again.");
    };

    reader.readAsText(uploadedFile);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        if (!open) {
          // Reset error message if dialog is closed.
          setErrorMessage(null);
        }
        onOpenChange(open);
      }}
    >
      <DialogContent className="flex flex-col gap-6">
        <DialogTitle>Upload a CSV</DialogTitle>
        <DialogDescription className="text-sm text-gray-500">
          Ensure the uploaded CSV file has a column named "Company Name" which
          contains the names of the Accounts. You can upload a maximum of 20
          accounts at once.
        </DialogDescription>
        {errorMessage && (
          <Label className="text-destructive">{errorMessage}</Label>
        )}

        <div className="w-full flex flex-col justify-center gap-6">
          <FileUpload onFileUpload={handleFileUpload} />
          <div className="flex flex-col gap-1">
            <p className="text-sm text-gray-500">
              Select the product to use for prospecting
            </p>
            <ProductSelection
              defaultValue=""
              onValueChange={setSelectedProduct}
              products={products}
            />
          </div>
          <div className="flex justify-center gap-2">
            <Button
              disabled={!uploadedFile || loading}
              onClick={handleSubmit}
              className="shadow-sm"
            >
              Submit
            </Button>
          </div>
          {loading && <ScreenLoader />}
        </div>
      </DialogContent>
    </Dialog>
  );
};

interface AddAccountManuallyProps {
  products: Product[];
  open: DialogProps["open"];
  onOpenChange: DialogProps["onOpenChange"];
  onSuccessfulAdd: (arg0: string) => void;
}

// Dialog that enables user to add an account manually.
const AddAccountManually: React.FC<AddAccountManuallyProps> = ({
  products,
  open,
  onOpenChange,
  onSuccessfulAdd,
}) => {
  const formSchema = z.object({
    accountName: z.string().min(1),
    productId: z.string().min(1),
  });

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      accountName: "",
      productId: "",
    },
  });

  const onSubmit = (updatedForm: z.infer<typeof formSchema>) => {
    form.reset();
    // TODO: call server to create product.
    console.log("updated form: ", updatedForm);
    return onSuccessfulAdd(updatedForm.accountName);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex flex-col gap-6">
        <DialogTitle>Enter Account Name</DialogTitle>
        <DialogDescription className="text-sm text-gray-500">
          Enter the Account name and select the product to use for prospecting.
        </DialogDescription>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="flex flex-col gap-6">
              <FormField
                control={form.control}
                name="accountName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-gray-800">
                      Account Name
                    </FormLabel>
                    <FormDescription></FormDescription>
                    <FormControl>
                      <Input
                        placeholder="e.g., Stripe, Rippling"
                        className="border-gray-300 rounded-md"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="productId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-gray-800">Product</FormLabel>
                    <FormDescription>
                      Select the Product that you are prospecting for.
                    </FormDescription>
                    <ProductSelection
                      defaultValue={field.value}
                      onValueChange={field.onChange}
                      products={products}
                    />
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Footer Navigation */}
            <DialogFooter className="mt-6">
              <Button type="submit">Submit</Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

// Main component to allow users to input accounts.
const AddAccounts: React.FC<{ products: Product[] }> = ({ products }) => {
  const importCSVOption = "Import CSV";
  const addManuallyOption = "Add Manually";
  const [openCSVDialog, setOpenCSVDialog] = useState(false);
  const [openManualDialog, setOpenManualDialog] = useState(false);

  const handleSelection = (e: Event) => {
    const val = (e.target as HTMLElement).innerText;
    if (val === importCSVOption) {
      setOpenCSVDialog(true);
    } else if (val === addManuallyOption) {
      setOpenManualDialog(true);
    }
  };

  // User initiated dialog mode change.
  const handleCSVDialogOpenChamge = (newOpen: boolean) => {
    setOpenCSVDialog(newOpen);
  };

  // CSV imported successfully, close the dialog now.
  const handleCSVImported = (createdAccounts: Account[]) => {
    console.log("created accounts: ", createdAccounts);

    // Close the dialog.
    setOpenCSVDialog(false);

    // TODO: callback to accounts table to list accounts once again.
  };

  // User initiated dialog mode change.
  const handleManualDialogOpenChamge = (newOpen: boolean) => {
    setOpenManualDialog(newOpen);
  };

  const handleAccountAddedManually = (accountName: string) => {
    setOpenManualDialog(false);
    // TODO: call server with this information.
    console.log("account name: ", accountName);
  };

  const itemClassName =
    "flex hover:cursor-pointer focus:bg-gray-300 text-sm text-gray-600";
  return (
    <div className="flex">
      <DropdownMenu modal={!(openCSVDialog || openManualDialog)}>
        <DropdownMenuTrigger className="flex items-center px-3 py-2 gap-2 bg-[rgb(136,102,221)]  hover:bg-[rgb(122,92,198)] text-white shadow-md">
          <Plus size={16} />
          <p className="text-sm">Add Accounts</p>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-[10rem]">
          <DropdownMenuItem
            className={itemClassName}
            onSelect={handleSelection}
          >
            {importCSVOption}
          </DropdownMenuItem>
          <DropdownMenuItem
            className={itemClassName}
            onSelect={handleSelection}
          >
            {addManuallyOption}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ImportCSV
        products={products}
        open={openCSVDialog}
        onOpenChange={handleCSVDialogOpenChamge}
        onImported={handleCSVImported}
      />

      <AddAccountManually
        products={products}
        open={openManualDialog}
        onOpenChange={handleManualDialogOpenChamge}
        onSuccessfulAdd={handleAccountAddedManually}
      />
    </div>
  );
};

export default AddAccounts;
