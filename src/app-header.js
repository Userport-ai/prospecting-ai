import "./app-header.css";
import { Layout, Menu, Flex, Typography } from "antd";
import { UserOutlined, DashboardOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useState } from "react";

const { Header } = Layout;
const { Title } = Typography;
const templates_key = "templates";
const leads_key = "leads";
const dashboard_key = "dashboard";

const items = [
  {
    label: "Leads",
    key: leads_key,
    icon: <UserOutlined />,
  },
  {
    label: "Templates",
    key: templates_key,
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
  const [curMenuKey, setCurMenuKey] = useState(leads_key);
  return (
    <Header id="nav-header">
      <Flex id="nav-flex">
        <div id="nav-logo-title">
          <Title level={3}>Userport.ai</Title>
        </div>
        <Menu
          id="nav-menu"
          mode="horizontal"
          items={items}
          selectedKeys={[curMenuKey]}
          onClick={(e) => {
            if (e.key === leads_key) {
              setCurMenuKey(leads_key);
              navigate("/leads");
            } else if (e.key === templates_key) {
              setCurMenuKey(templates_key);
              navigate("/templates");
            }
          }}
        ></Menu>
      </Flex>
    </Header>
  );
}

export default AppHeader;
