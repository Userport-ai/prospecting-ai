import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSideBar";
import { Outlet } from "react-router";

export default function AppLayout({ children }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <main className="flex justify-start w-full">
        <SidebarTrigger />
        <Outlet />
      </main>
    </SidebarProvider>
  );
}
