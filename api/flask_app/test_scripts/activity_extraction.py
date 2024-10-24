import os
from markdownify import markdownify
from typing import Optional
from bs4 import BeautifulSoup
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.prompts import HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field


def convert_to_markdown(filename):
    page_html = ""
    with open(f"example_linkedin_info/extension_activity/{filename}.txt", "r") as f:
        page_html = f.read()

    # Heading style argument is passed in to ensure we get '#' formatted headings.
    page_md = markdownify(page_html, heading_style="ATX")

    with open(f"example_linkedin_info/extension_activity/{filename}_md.txt", "w") as f:
        f.write(page_md)


def parse_html(filename):
    page_html = ""
    with open(f"example_linkedin_info/extension_activity/{filename}.txt", "r") as f:
        page_html = f.read()

    soup = BeautifulSoup(page_html, "html.parser")
    logged_in_user_tags = soup.find_all("div", class_="member")

    for tag in logged_in_user_tags:
        print(tag)
        tag.clear()

        print("\n\nNEXT\n\n")

    clean_page_md = markdownify(str(soup), heading_style="ATX")

    activity_md_list = clean_page_md.split("* ## Feed post number")

    print("len: ", len(activity_md_list))
    for i in range(len(activity_md_list)):
        if i == 1:
            with open(f"example_linkedin_info/extension_activity/{filename}_userinfo_removed.txt", "w") as f:
                f.write(activity_md_list[i])
            break


def fetch_comment_summary(filename, person_name, company_name, person_role_title):
    OPENAI_API_KEY = os.environ["OPENAI_USERPORT_API_KEY"]
    OPENAI_GPT_4O_MODEL = os.environ["OPENAI_GPT_4O_MODEL"]
    OPENAI_GPT_4O_MINI_MODEL = os.environ["OPENAI_GPT_4O_MINI_MODEL"]
    OPENAI_REQUEST_TIMEOUT_SECONDS = 20

    comment_md = ""
    with open(f"example_linkedin_info/extension_activity/{filename}.txt", "r") as f:
        comment_md = f.read()

    SYSTEM_MESSAGE = SystemMessage(content=(
        "You are a very smart and truthful sales person that analyzes LinkedIn comments made by your prospect to extract useful information about their recent activities\n"
        "You will be given your prospect's name, the company they work at and their current role.\n"
        "You will also be given a text in Markdown format that represents a LinkedIn post and a comment made by your prospect on this post.\n"
        "The text will be delimited by triple quotes.\n"
        "Your job is to answer the user's question using the information found in the text.\n"
        ""
    ))

    human_message_prompt_template = (
        "**Prospect Details:**\n"
        "Name: {person_name}\n"
        "Company: {company_name}\n"
        "Role Title: {person_role_title}\n"
        "\n\n"
        '"""{comment_md}"""'
        "\n\n"
        "Question: {question}"
    )
    human_message_prompt = HumanMessagePromptTemplate.from_template(
        human_message_prompt_template)

    prompt = ChatPromptTemplate.from_messages(
        [
            SYSTEM_MESSAGE,
            human_message_prompt,
        ]
    )

    class LinkedInCommentDetails(BaseModel):
        publish_date: Optional[str] = Field(
            default=None, description="publish date of the post.")
        detailed_summary: Optional[str] = Field(
            default=None, description="Detailed Summary of the post.")

    llm = ChatOpenAI(temperature=0, model_name=OPENAI_GPT_4O_MODEL,
                     api_key=OPENAI_API_KEY, timeout=OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(LinkedInCommentDetails)

    chain = prompt | llm
    question = (
        "Extract the date when the post was published and provide a detailed summary explaining the post.\n"
        "The publish date is usually in one of the following formats: 5d, 1mo, 2yr, 3w etc.\n"
        "Include details like names, titles, numbers, metrics and the comment left by the prospect in the detailed summary wherever possible.\n"
    )
    result: LinkedInCommentDetails = chain.invoke({
        "person_name": person_name,
        "company_name": company_name,
        "person_role_title": person_role_title,
        "comment_md": comment_md,
        "question": question,
    })

    print(result)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.dev")

    filename = "comments_1_userinfo_removed"
    person_name = "Aakarshan Chawla"
    company_name = "Rippling"
    person_role_title = "Director, Sales"

    convert_to_markdown("reactions_3")
    # parse_html("comments_1")
    # fetch_comment_summary(
    #     filename=filename, person_name=person_name, company_name=company_name, person_role_title=person_role_title)
