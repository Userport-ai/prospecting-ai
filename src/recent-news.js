import "./recent-news.css";
import { Flex, Button, Card, Typography, Tooltip, Modal } from "antd";
import { useContext, useState } from "react";
import { AuthContext } from "./root";

const { Text, Link } = Typography;

// Represents Highlight from the leads' news.
function Highlight({ lead_research_report_id, highlight, onEmailCreation }) {
  const [createEmailLoading, setCreateEmailLoading] = useState(false);

  const { user } = useContext(AuthContext);
  // Handles request by user to personalize a given news item for given lead.
  async function handlePersonalizeRequest() {
    setCreateEmailLoading(true);
    // Call server to create personalization using given highlight.
    const idToken = await user.getIdToken();
    const response = await fetch(
      "/api/v1/lead-research-reports/personalized-emails",
      {
        method: "POST",
        body: JSON.stringify({
          lead_research_report_id: lead_research_report_id,
          highlight_id: highlight.id,
        }),
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + idToken,
        },
      }
    );
    // TODO: Handle non JSON response error.
    // Hints: response.ok: false and response.status: 400/500 and statusText: error msg.
    const result = await response.json();
    if (result.status === "error") {
      // Show error to the user in a Modal.
      var title = "Error creating email!";
      var description = result.message;
      if (result.status_code === 429) {
        if (result.message.includes("minute")) {
          title = "Error! Too many requests at once!";
          description = "Please wait for a few minutes and retry.";
        } else if (result.message.includes("day")) {
          title = "Error! Limit exhausted!";
          description =
            "Exceeded email creation limit for the day, please try again in 24 hours.";
        }
      }
      Modal.error({
        title: title,
        content: description,
      });
      setCreateEmailLoading(false);
      return;
    }
    setCreateEmailLoading(false);
    onEmailCreation(result.personalized_email);
  }
  return (
    <Card>
      <div className="card-category-container">
        <Text strong className="card-category">
          {highlight.category_readable_str}
        </Text>
        <Tooltip title="AI will automatically create a personalized outreach message for your lead using this news item as source.">
          <Button
            className="personalize-btn"
            onClick={handlePersonalizeRequest}
            loading={createEmailLoading}
          >
            Use for outreach
          </Button>
        </Tooltip>
      </div>
      <div className="card-citation-link-container">
        <Text className="card-citation-source-label" strong>
          Source:{" "}
        </Text>
        <Link
          className="card-citation-link"
          href={highlight.url}
          target="_blank"
        >
          {highlight.url}
        </Link>
      </div>
      <div className="card-date-container">
        <Text className="card-date-label" strong>
          Publish Date:{" "}
        </Text>
        <Text className="card-date">{highlight.publish_date_readable_str}</Text>
      </div>
      <div className="card-text-container">
        <Text className="card-text-label" strong>
          Summary
        </Text>
        <Text className="card-text">{highlight.concise_summary}</Text>
      </div>
    </Card>
  );
}

// Represents recent news as Categories and associated highlights.
function RecentNews({ lead_research_report_id, details, onEmailCreation }) {
  var initialSelectedCategories = [];
  if (details.length > 0) {
    initialSelectedCategories = [details[0].category_readable_str];
  }
  const [categoriesSelected, setCategoriesSeleted] = useState(
    initialSelectedCategories
  );

  function handleCategoryClicked(category) {
    if (categoriesSelected.filter((cat) => cat === category).length === 0) {
      // Category not selected yet, prepend to selection.
      setCategoriesSeleted([category, ...categoriesSelected]);
    } else {
      // Category already selected, remove it.
      setCategoriesSeleted(
        categoriesSelected.filter((cat) => cat !== category)
      );
    }
  }

  return (
    <>
      <Flex id="report-details-container" vertical={false} wrap gap="large">
        {/* These are the categories */}
        {details.map((detail) => {
          let categoryBtnClass = categoriesSelected.includes(
            detail.category_readable_str
          )
            ? "category-btn-selected"
            : "category-btn";
          return (
            <Button
              key={detail.category}
              className={categoryBtnClass}
              type="primary"
              onClick={(e) => handleCategoryClicked(e.target.innerText)}
            >
              {detail.category_readable_str}
            </Button>
          );
        })}
        {/* These are the highlights from selected categories. */}
        {categoriesSelected
          .map(
            (selectedCategory) =>
              // Filtered category guaranteed to exist and size 1 since selected categories
              // are from the same details array.
              details.filter(
                (detail) => detail.category_readable_str === selectedCategory
              )[0]
          )
          .flatMap((detail) =>
            detail.highlights.map((highlight) => (
              <Highlight
                key={highlight.id}
                lead_research_report_id={lead_research_report_id}
                highlight={highlight}
                onEmailCreation={onEmailCreation}
              />
            ))
          )}
      </Flex>
    </>
  );
}

// function RecentNews({ details }) {
//   return (
//     <Flex id="report-details-container" vertical={false} wrap gap="large">
//       <CategoriesAndHighlights details={details} />
//     </Flex>
//   );
// }

export default RecentNews;
