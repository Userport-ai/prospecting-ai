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
    <Sidebar className="shadow-2xl">
      <SidebarHeader className="hover:bg-secondary hover:cursor-pointer m-2">
        <div className="w-36">
          <img
            className="scale-100"
            src={logo}
            alt="userport-logo"
            onClick={() => navigate("/accounts")}
          />
        </div>
      </SidebarHeader>
      <SidebarSeparator className="border-t-2 border-gray-200" />
      <SidebarContent className="mt-5 px-2">
        <SidebarGroup>
          <SidebarGroupLabel className="text-gray-500">App</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="flex flex-col gap-2">
              {appItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <a href={item.url}>
                      <item.icon />
                      <span className="text-gray-600 font-inter font-medium">
                        {item.title}
                      </span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>

          <SidebarGroupLabel className="text-gray-500 mt-10">
            Getting Started
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {onboardingItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <a href={item.url}>
                      <item.icon />
                      <span className="text-gray-600 font-inter font-medium">
                        {item.title}
                      </span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton>
                  <User2 />
                  <p className="text-gray-600 font-inter font-medium">
                    Addarsh
                  </p>
                  <ChevronUp className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                className="w-[--radix-popper-anchor-width]"
              >
                <DropdownMenuItem className="hover:cursor-pointer">
                  <span>Account</span>
                </DropdownMenuItem>
                <DropdownMenuItem className="hover:cursor-pointer">
                  <span>Billing</span>
                </DropdownMenuItem>
                <DropdownMenuItem className="hover:cursor-pointer">
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
