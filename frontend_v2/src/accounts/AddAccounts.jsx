import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AddAccounts() {
  return (
    <div className="flex">
      <Button
        onClick={() => console.log("add row top")}
        className="flex items-center px-3 py-2 gap-2 bg-[rgb(136,102,221)]  hover:bg-[rgb(122,92,198)] text-white shadow-md"
      >
        <Plus size={18} />
        Add Accounts
      </Button>
    </div>
  );
}
