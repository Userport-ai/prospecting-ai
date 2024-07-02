import "./header.css";
import { Layout, Menu, Flex, Typography } from "antd";
import { UserOutlined, DashboardOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";

const { Header } = Layout;
const { Title } = Typography;
const icp_key = "icp";
const dashboard_key = "dashboard";

const items = [
  {
    label: "ICP",
    key: icp_key,
    icon: <UserOutlined />,
  },
  {
    label: "Dashboard",
    key: dashboard_key,
    icon: <DashboardOutlined />,
  },
];

function AppHeader() {
  const navigate = useNavigate();
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
          selectedKeys={[icp_key]}
          onClick={(e) => {
            if (e.key === icp_key) {
              // Navigate to default page.
              navigate("/");
            }
          }}
        ></Menu>
      </Flex>
    </Header>
  );
}

export default AppHeader;
