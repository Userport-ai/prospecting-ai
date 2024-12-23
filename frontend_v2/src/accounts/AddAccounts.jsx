import { useState } from "react";
import { Plus, Upload, FileIcon, XCircle } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogTitle, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogDescription } from "@radix-ui/react-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Component to let user upload a file from their computer.
export function FileUpload({ onFileUpload }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [dragging, setDragging] = useState(false);

  // Returns true if valid file type and false otherwise.
  const isValidFileType = (file) => {
    return file.type === "text/csv" ? true : false;
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!isValidFileType(file)) {
        setErrorMessage(`Error! ${file.name} has invalid file type!`);
        setSelectedFile(null);
      } else {
        setSelectedFile(file);
        setErrorMessage(null);
      }
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => {
    setDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) {
      if (!isValidFileType(file)) {
        setErrorMessage(`Error! ${file.name} has invalid file type!`);
        setSelectedFile(null);
      } else {
        setSelectedFile(file);
        setErrorMessage(null);
      }
    }
  };

  // Handle Submit of uploaded file.
  const handleSubmit = () => {
    return onFileUpload(selectedFile);
  };

  return (
    <div className="flex flex-col gap-4">
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
          onDrop={handleDrop}
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
            <span className="text-sm">
              {selectedFile
                ? selectedFile.name
                : "Drag & Drop or Click to Upload"}
            </span>
          </Label>
        </div>
      )}

      {/* Display error if any. */}
      {errorMessage && <Label className="text-red-600">{errorMessage}</Label>}

      {/* When file is successfully uploaded. */}
      {selectedFile && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-4 border border-gray-200 bg-gray-50 rounded-md px-4 py-2">
            <FileIcon className="text-gray-600" size={24} />
            <span className="text-sm text-gray-700">{selectedFile.name}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedFile(null)}
              className="text-red-500 hover:bg-red-50"
            >
              <XCircle size={18} />
              Remove
            </Button>
          </div>
          {/* Action Buttons */}
          <div className="flex justify-center gap-2">
            <Button
              disabled={!selectedFile}
              onClick={handleSubmit}
              className="shadow-sm"
            >
              Submit
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// Dialog that enables user to import CSV
function ImportCSV({ open, onOpenChange, onImported }) {
  const handleFileUpload = (file) => {
    console.log("Uploaded file:", file);
    // TODO: Send file to server to validate.
    // Once it is validated, close the dialog.
    onImported();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex flex-col gap-6">
        <DialogTitle>Upload a CSV</DialogTitle>
        <DialogDescription className="text-sm text-gray-500">
          Make sure the CSV file has atleast one column that contains the
          Account website. We will use the website identify and enrich accounts.
        </DialogDescription>

        <div className="w-full flex justify-center">
          {/* <Button className="w-fit p-2">Upload CSV</Button> */}
          <FileUpload onFileUpload={handleFileUpload} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function AddAccounts() {
  const importCSVOption = "Import CSV";
  const addManuallyOption = "Add Manually";
  const [open, setOpen] = useState(false);

  const handleSelection = (e) => {
    const val = e.target.innerText;
    if (val === importCSVOption) {
      setOpen(true);
    }
  };

  // User initiated dialog mode change.
  const handleDialogOpenChamge = (newOpen) => {
    setOpen(newOpen);
  };

  // CSV imported successfully, close the dialog now.
  const handleCSVImported = () => {
    // Close the dialog.
    setOpen(false);

    // TODO: callback to accounts table to fetch uploaded rows.
  };

  const itemClassName =
    "flex hover:cursor-pointer focus:bg-gray-300 text-md text-gray-600";
  return (
    <div className="flex">
      <DropdownMenu modal={!open}>
        <DropdownMenuTrigger className="flex items-center px-3 py-2 gap-2 bg-[rgb(136,102,221)]  hover:bg-[rgb(122,92,198)] text-white shadow-md">
          <Plus size={18} />
          <p>Add Accounts</p>
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
        open={open}
        onOpenChange={handleDialogOpenChamge}
        onImported={handleCSVImported}
      />
    </div>
  );
}
