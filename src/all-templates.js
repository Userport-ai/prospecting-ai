import "./all-templates.css";
import { Card, Flex, Typography, Button } from "antd";
import { useNavigate } from "react-router-dom";

const { Text, Title } = Typography;

const templateMessage = `Being a tech leader and handling a team of 30+ engineers, does your team face challenges with searching of info scattered across different internals apps, outside coding?\n
Asking this as speaking with some of our engineering customers like X and Y , I've learned that a major challenge facing engineering teams today is productivity being hindered by time spent searching for technical documentation within the SDLC, but no worries- Glean solves this problem and much more!\n
To save your team from spending 20% of every workday looking for information, do you mind spending 20 mins to see Glean in action?`;

function AllTemplates() {
  const navigate = useNavigate();
  function addLineBreaks(text) {
    return text.split("\n").map((substr) => {
      return (
        <>
          {substr}
          <br />
        </>
      );
    });
  }

  return (
    <div id="all-templates-outer">
      <Flex id="all-templates-outer-container" vertical={true} gap="middle">
        <Title level={3}>Template Messages</Title>
        <Card>
          <Flex vertical={true} gap="middle">
            <Flex vertical={false} gap="small">
              <Text className="card-key">Role Titles:</Text>
              <Text>CMO</Text>
            </Flex>
            <Flex vertical={false} gap="small">
              <Text className="card-key">Additional Keywords:</Text>
              <Text>None</Text>
            </Flex>
            <Flex vertical={true} gap="small">
              <Text className="card-key">Message:</Text>
              <Text>{addLineBreaks(templateMessage)}</Text>
            </Flex>
          </Flex>
        </Card>
        <Flex vertical={false} justify="flex-end">
          <Button
            type="primary"
            htmlType="submit"
            // TODO: change to use action and send data to server
            onClick={() => navigate("/lead-result")}
          >
            Add new template
          </Button>
        </Flex>
      </Flex>
    </div>
  );
}

export default AllTemplates;
