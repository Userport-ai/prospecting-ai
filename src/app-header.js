import "./app-header.css";
import { Layout, Menu, Typography } from "antd";
import { UserOutlined, SettingOutlined } from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "./root";
import { usePostHog } from "posthog-js/react";

const { Header } = Layout;
const { Link } = Typography;
const templates_key = "templates";
const leads_key = "leads";
const account_key = "account";
const logout_key = "logout";

const items = [
  {
    label: <Link href="/leads">Leads</Link>,
    key: leads_key,
    icon: <UserOutlined />,
  },
  {
    label: <Link href="/templates">Templates</Link>,
    key: templates_key,
    icon: <UserOutlined />,
  },
  {
    label: "Account",
    key: account_key,
    icon: <SettingOutlined />,
    children: [
      {
        label: "Logout",
        key: logout_key,
      },
    ],
  },
];

function AppHeader() {
  const { handleLogout } = useContext(AuthContext);
  const location = useLocation();
  const curMenuKey = location.pathname.includes("template")
    ? templates_key
    : leads_key;
  const navigate = useNavigate();
  const posthog = usePostHog();

  return (
    <Header id="nav-header">
      <div id="nav-logo-container">
        <img
          src="/combination_mark_complementary.png"
          alt="userport-complementary-logo"
          onClick={() => navigate("/leads")}
        />
      </div>
      <Menu
        id="nav-menu"
        mode="horizontal"
        items={items}
        selectedKeys={[curMenuKey]}
        onClick={(e) => {
          if (e.key === leads_key) {
            // Send event.
            posthog.capture("leads_tab_clicked");
            return navigate("/leads");
          } else if (e.key === templates_key) {
            // Send event.
            posthog.capture("templates_tab_clicked");
            return navigate("/templates");
          } else if (e.key === logout_key) {
            return handleLogout();
          }
        }}
      ></Menu>
    </Header>
  );
}

export default AppHeader;
