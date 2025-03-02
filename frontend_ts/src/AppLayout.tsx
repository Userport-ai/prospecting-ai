import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { Outlet } from "react-router";

// Need this interface to fix compilation error.
// Solution found here: https://github.com/shadcn-ui/ui/issues/5509
interface CustomCSSProperties extends React.CSSProperties {
  "--sidebar-width"?: string;
}

export default function AppLayout() {
  return (
    <SidebarProvider
      defaultOpen={false}
      style={{ "--sidebar-width": "12rem" } as CustomCSSProperties}
    >
      <AppSidebar />
      <main className="w-full">
        <SidebarTrigger />
        <Outlet />
      </main>
    </SidebarProvider>
  );
}
