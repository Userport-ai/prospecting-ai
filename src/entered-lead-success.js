import "./entered-lead-success.css";
import { useLoaderData, useNavigate, useNavigation } from "react-router-dom";
import { Button, ConfigProvider, Result, Skeleton, Typography } from "antd";

const { Text, Link } = Typography;

export function enteredLeadSuccessLoader({ request }) {
  const url = new URL(request.url);
  const linkedin_url = url.searchParams.get("url");
  return linkedin_url;
}

function EnteredLeadSuccess() {
  const linkedin_url = useLoaderData();
  const navigate = useNavigate();
  const component_is_loading = useNavigation().state !== "idle";

  if (component_is_loading) {
    return (
      <Skeleton
        active
        paragraph={{
          rows: 15,
        }}
      />
    );
  }

  function SubTitle() {
    return (
      <div id="lead-sucess-subtitle-container">
        <div>
          <Text className="text-no-link">Started research for lead URL: </Text>
          <Link href={linkedin_url} target="_blank">
            {linkedin_url}
          </Link>
          <Text className="text-no-link"> in the background</Text>
        </div>
        <Text className="text-no-link">
          It usually takes 5-10 minutes for it to complete. You can check the
          status in the Leads table.
        </Text>
        <Text className="text-no-link">
          Once the status says "Ready", you will able to view the Research
          Results.
        </Text>
        <Text className="text-no-link">
          In the meantime, you can continue adding more leads.
        </Text>
      </div>
    );
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          // Styling for buttons.
          // Seed Token
          colorPrimary: "#65558f",
        },
      }}
    >
      <Result
        status="success"
        title={
          <h1 id="lead-success-title">Successfully started Lead Research!</h1>
        }
        subTitle={<SubTitle />}
        extra={[
          <Button type="primary" onClick={() => navigate("/leads")}>
            Back to Leads table
          </Button>,
          <Button onClick={() => navigate("/leads/create")}>
            Add another Lead
          </Button>,
        ]}
      ></Result>
    </ConfigProvider>
  );
}

export default EnteredLeadSuccess;
