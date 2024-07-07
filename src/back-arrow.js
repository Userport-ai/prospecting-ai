import "./back-arrow.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";

function BackArrow() {
  const navigate = useNavigate();
  return <ArrowLeftOutlined onClick={() => navigate(-1)} />;
}

export default BackArrow;
