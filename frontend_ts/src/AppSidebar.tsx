import { List, ChevronUp, User2, UsersRound, NotebookPen } from "lucide-react";
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
import { Link, useLocation, useNavigate } from "react-router";
import { AuthContext, handleLogout, useAuthContext } from "./auth/AuthProvider";

// App items.
const appItems = [
  {
    key: "accounts",
    title: "Accounts",
    url: "/accounts",
    icon: List,
    isActive: false,
  },
  {
    key: "leads",
    title: "Leads",
    url: "/leads",
    icon: UsersRound,
    isActive: false,
  },
  {
    key: "products",
    title: "Products",
    url: "/products",
    icon: NotebookPen,
    isActive: false,
  },
];

// Get user's first name.
const getUserFirstName = (authContext: AuthContext): string | null => {
  if (!authContext.firebaseUser) {
    return null;
  }
  const displayName = authContext.firebaseUser.displayName;
  if (!displayName) {
    return null;
  }
  return displayName.split(" ")[0];
};

export function AppSidebar() {
  const authContext = useAuthContext();
  const navigate = useNavigate();
  const location = useLocation();
  var activeItemMarked = false;
  appItems.forEach((item) => {
    if (activeItemMarked || !location.pathname.includes(item.key)) {
      // When there are multiple active items e.g. accounts/:id/leads,
      // we only want to mark the first one as active. All other items
      // should be marked inactive so that sidebar only has 1 active items
      // at a time.
      item.isActive = false;
    } else {
      item.isActive = true;
      activeItemMarked = true;
    }
  });

  const logoutOptionText = "Log Out";
  const handleFooterMenuSelection = (e: Event) => {
    const selectedOption = (e.target as HTMLElement).innerText;
    if (selectedOption === logoutOptionText) {
      // Logout user.
      handleLogout();
    }
  };

  return (
    <Sidebar className="shadow-2xl bg-sidebar-background text-sidebar-foreground h-full min-h-screen">
      {/* Header */}
      <SidebarHeader className="flex items-center justify-center p-4 hover:cursor-pointer transition">
        <div className="w-36">
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
          <SidebarGroupContent>
            <SidebarMenu className="space-y-2">
              {appItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={item.isActive}>
                    <Link
                      to={item.url}
                      className="flex items-center gap-4 p-3 rounded-md hover:bg-primary hover:text-primary-foreground transition"
                    >
                      <item.icon className="w-5 h-5" />
                      <span className="font-medium">{item.title}</span>
                    </Link>
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
                  <p className="font-medium">{getUserFirstName(authContext)}</p>
                  <ChevronUp className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                className="w-[--radix-popper-anchor-width] shadow-lg bg-card text-card-foreground rounded-md p-2"
              >
                <DropdownMenuItem
                  className="hover:bg-muted hover:cursor-pointer rounded-md p-2"
                  onSelect={handleFooterMenuSelection}
                >
                  <span>{logoutOptionText}</span>
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
