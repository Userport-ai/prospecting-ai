import "./recent-news.css";
import { Flex, Button, Card, Typography } from "antd";
import { useState } from "react";

const { Text, Link } = Typography;

// Represents Highlight from the leads' news.
function Highlight({ highlight }) {
  return (
    <Card>
      <div>
        <Text strong className="card-category">
          {highlight.category_readable_str}
        </Text>
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

// Represents Categories buttons and associated highlights.
function CategoriesAndHighlights({ details }) {
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
            <Highlight key={highlight.id} highlight={highlight} />
          ))
        )}
    </>
  );
}

function RecentNews({ details }) {
  return (
    <Flex id="report-details-container" vertical={false} wrap gap="large">
      <CategoriesAndHighlights details={details} />
    </Flex>
  );
}

export default RecentNews;
