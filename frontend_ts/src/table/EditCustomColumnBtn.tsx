import { CustomColumn, getCustomColumn } from "@/services/CustomColumn";
import { useAuthContext } from "@/auth/AuthProvider";
import { useToast } from "@/hooks/use-toast";
import { useState } from "react";
import { Loader2, Pencil } from "lucide-react";

const EditCustomColumnBtn: React.FC<{
  columnId: string;
  onCustomColumnFetch: (customColumn: CustomColumn) => void;
}> = ({ columnId, onCustomColumnFetch }) => {
  const authContext = useAuthContext();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const customColumn = await getCustomColumn(authContext, columnId);
      onCustomColumnFetch(customColumn);
    } catch (error) {
      console.error(
        `Failed to fetch custom column with ID: ${columnId} lead generation with error: ${error}`
      );
      // Show toast.
      toast({
        variant: "destructive",
        title: "Uh oh! Something went wrong.",
        description: "Could not Edit Ask AI column, please contact support!",
      });
    } finally {
      setLoading(false);
    }
  };

  return loading ? (
    <Loader2 size={16} className="h-4 w-4 mr-2 animate-spin text-yellow-400" />
  ) : (
    <Pencil
      className="hover:cursor-pointer hover:text-yellow-300"
      onClick={handleClick}
      size={16}
    />
  );
};

export default EditCustomColumnBtn;
