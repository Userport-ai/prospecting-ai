import "./header.css";
import { Layout, Menu, Flex } from "antd";
import { UserOutlined, DashboardOutlined } from "@ant-design/icons";

const { Header } = Layout;

const items = [
  {
    label: "ICP",
    key: "icp",
    icon: <UserOutlined />,
  },
  {
    label: "Dashboard",
    key: "dashboard",
    icon: <DashboardOutlined />,
  },
];

function AppHeader() {
  return (
    <Header id="nav-header">
      <Flex id="nav-flex">
        <div id="nav-logo-title">
          <h2>Prospecting AI</h2>
        </div>
        <Menu
          id="nav-menu"
          mode="horizontal"
          items={items}
          selectedKeys={["icp"]}
        ></Menu>
      </Flex>
    </Header>
  );
}

export default AppHeader;
