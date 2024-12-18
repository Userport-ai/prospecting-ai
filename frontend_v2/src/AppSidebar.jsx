import {
  ChartNoAxesColumn,
  List,
  Settings,
  ChevronUp,
  User2,
  UsersRound,
  NotebookPen,
  File,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
  SidebarRail,
  SidebarHeader,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import logo from "./assets/combination_mark_primary_sidebar.png";
import { useNavigate } from "react-router";

// App items.
const appItems = [
  {
    title: "Accounts",
    url: "#",
    icon: List,
  },
  {
    title: "Leads",
    url: "#",
    icon: UsersRound,
  },
  {
    title: "Analytics",
    url: "#",
    icon: ChartNoAxesColumn,
  },
  {
    title: "Playbook",
    url: "#",
    icon: NotebookPen,
    isActive: true,
  },
  {
    title: "Settings",
    url: "#",
    icon: Settings,
  },
];

// Onboarding items.
const onboardingItems = [
  {
    title: "Documentation",
    url: "#",
    icon: File,
  },
];
export function AppSidebar() {
  const navigate = useNavigate();

  return (
    <Sidebar className="shadow-2xl bg-sidebar-background text-sidebar-foreground h-full min-h-screen">
      {/* Header */}
      <SidebarHeader className="flex items-center justify-center p-4 hover:bg-secondary hover:cursor-pointer transition">
        <div className="w-40">
          <img
            className="scale-100"
            src={logo}
            alt="userport-logo"
            onClick={() => navigate("/accounts")}
          />
        </div>
      </SidebarHeader>
      <SidebarSeparator className="border-t-2 border-sidebar-border" />

      {/* Sidebar Content */}
      <SidebarContent className="mt-5 px-4 space-y-8">
        {/* App Group */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-4">
            App
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-2">
              {appItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={item.isActive}>
                    <a
                      href={item.url}
                      className="flex items-center gap-4 p-3 rounded-md hover:bg-primary hover:text-primary-foreground transition"
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium">{item.title}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Getting Started Group */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-4">
            Getting Started
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-2">
              {onboardingItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <a
                      href={item.url}
                      className="flex items-center gap-4 p-3 rounded-md hover:bg-secondary hover:text-secondary-foreground transition"
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium">{item.title}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer */}
      <SidebarFooter className="mt-auto p-4 border-t border-sidebar-border">
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton className="flex items-center gap-4 p-3 rounded-md hover:bg-muted hover:text-muted-foreground transition">
                  <User2 className="w-5 h-5" />
                  <p className="font-medium">Addarsh</p>
                  <ChevronUp className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                className="w-[--radix-popper-anchor-width] shadow-lg bg-card text-card-foreground rounded-md p-2"
              >
                <DropdownMenuItem className="hover:bg-muted hover:cursor-pointer rounded-md p-2">
                  <span>Account</span>
                </DropdownMenuItem>
                <DropdownMenuItem className="hover:bg-muted hover:cursor-pointer rounded-md p-2">
                  <span>Billing</span>
                </DropdownMenuItem>
                <DropdownMenuItem className="hover:bg-muted hover:cursor-pointer rounded-md p-2">
                  <span>Sign out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
