import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "./components/ui/dropdown-menu";
import logo from "./assets/combination_mark_complementary.png";
import { useNavigate } from "react-router";

function Header() {
  const navigate = useNavigate();

  return (
    <header className="bg-primary w-full shadow-md border-b border-gray-200">
      <div className="w-full mx-0 flex items-center justify-between py-4 px-6">
        <div className="w-44 h-11 bg-green-800 -mt-36">
          <img
            className="hover:cursor-pointer"
            src={logo}
            alt="userport-complementary-logo"
            onClick={() => navigate("/accounts")}
          />
        </div>

        {/* Profile Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center space-x-2 border rounded-md px-3 py-1">
              <span className="text-primary-foreground">Profile</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem
              className="hover:cursor-pointer"
              onClick={() => alert("Account Settings")}
            >
              Account Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              className="hover:cursor-pointer"
              onClick={() => alert("Sign Out")}
            >
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

export default Header;
