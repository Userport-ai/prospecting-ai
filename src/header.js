import "./header.css";
import { Layout, Menu, Flex, Typography } from "antd";
import { UserOutlined, DashboardOutlined } from "@ant-design/icons";

const { Header } = Layout;
const { Title } = Typography;

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
          <Title level={3}>Prospecting AI</Title>
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
