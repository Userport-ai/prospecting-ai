import {
  ChartNoAxesColumn,
  List,
  Settings,
  ChevronUp,
  User2,
  UsersRound,
  NotebookPen,
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
} from "./components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "./components/ui/dropdown-menu";
import logo from "./assets/combination_mark_primary.png";
import { useNavigate } from "react-router";

// Menu items.
const items = [
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

export function AppSidebar() {
  const navigate = useNavigate();
  return (
    <Sidebar>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>
            <div className="w-40 h-10 -mt-28">
              <img
                className="hover:cursor-pointer -mx-2"
                src={logo}
                alt="userport-logo"
                onClick={() => navigate("/accounts")}
              />
            </div>
          </SidebarGroupLabel>
          <SidebarGroupContent className="mt-10">
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <a href={item.url}>
                      <item.icon />
                      <span>{item.title}</span>
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
                  Addarsh
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
    </Sidebar>
  );
}
