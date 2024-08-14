import "./select-template-modal.css";
import { Modal, Select, Typography } from "antd";
import { useContext, useState } from "react";
import { AuthContext } from "./root";

const { Text } = Typography;

// Replace newlines with HTML break tags.
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

// Modal that allows selection of email templates by user.
function SelectTemplateModal({
  modalOpen,
  outreachTemplates,
  onSelect,
  onCancel,
}) {
  const { user } = useContext(AuthContext);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);

  const templateOptions = outreachTemplates.map((template) => {
    return { label: template.name, value: template.id };
  });

  const selectedTemplateMessage =
    selectedTemplateId !== null
      ? outreachTemplates.find((t) => t.id === selectedTemplateId).message
      : null;

  if (!user) {
    // User is logged out, return immediately.
    return null;
  }

  const handleOk = () => {
    onSelect();
  };
  const handleCancel = () => {
    onCancel();
  };

  function handleTemplateSelection(value, option) {
    setSelectedTemplateId(value);
  }

  function TemplateMessage({ selectedTemplateId }) {
    if (selectedTemplateId === null) {
      return null;
    }
    return (
      <div id="selected-template-message-container">
        <Text id="message-label">Message</Text>
        <Text>{addLineBreaks(selectedTemplateMessage)}</Text>
      </div>
    );
  }

  return (
    <Modal
      className="select-template-modal"
      title="Select Template"
      open={modalOpen}
      onOk={handleOk}
      okText={"Select"}
      onCancel={handleCancel}
    >
      <Select options={templateOptions} onChange={handleTemplateSelection} />
      <TemplateMessage selectedTemplateId={selectedTemplateId} />
    </Modal>
  );
}

export default SelectTemplateModal;
