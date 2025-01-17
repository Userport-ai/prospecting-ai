import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarProvider,
  useSidebar,
} from "@/components/ui/sidebar";
import { X } from "lucide-react";
import { ReactNode } from "react";

const CellSidebar: React.FC<{ contentNode: ReactNode }> = ({ contentNode }) => {
  const { setOpen } = useSidebar();
  return (
    <Sidebar side="right" variant="floating">
      <SidebarHeader>
        <div className="flex justify-end">
          <X className="hover:cursor-pointer" onClick={() => setOpen(false)} />
        </div>
      </SidebarHeader>
      <SidebarContent>{contentNode}</SidebarContent>
    </Sidebar>
  );
};

interface CellExpansionSidebarProps {
  contentNode: ReactNode | null;
  onOpenChange: (open: boolean) => void;
}

// Sidebar that displays detailed information of a Cell in a Table.
const CellExpansionSidebar: React.FC<CellExpansionSidebarProps> = ({
  contentNode,
  onOpenChange,
}) => {
  return (
    <SidebarProvider open={contentNode !== null} onOpenChange={onOpenChange}>
      <CellSidebar contentNode={contentNode} />
    </SidebarProvider>
  );
};

export default CellExpansionSidebar;
