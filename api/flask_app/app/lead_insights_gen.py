import os
import logging
from app.models import LeadResearchReport, ContentDetails
from langchain_core.messages import SystemMessage
from app.database import Database
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import HumanMessagePromptTemplate
from typing import List, Optional
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.callbacks import get_openai_callback
from langchain_openai import ChatOpenAI
from app.models import OpenAITokenUsage

logger = logging.getLogger()


class LeadInsights:
    """Helps to generate lead insights given list of content details and information about the lead."""

    def __init__(self, lead_research_report_id: str, person_name: str, company_name: str, company_description: str, person_role_title: str, person_about_me: Optional[str]) -> None:
        # Constants.
        self.OPENAI_API_KEY = os.environ["OPENAI_USERPORT_API_KEY"]
        self.OPENAI_GPT_4O_MINI_MODEL = os.environ["OPENAI_GPT_4O_MINI_MODEL"]
        self.OPENAI_REQUEST_TIMEOUT_SECONDS = 20
        self.INSIGHTS_PROCESSING_TAG = "insights_processing"

        if person_about_me == None:
            person_about_me = "Not provided"

        self.lead_research_report_id = lead_research_report_id
        self.person_name = person_name
        self.company_name = company_name

        self.INSIGHT_SYSTEM_MESSAGE = SystemMessage(content=(
            "You are a very intelligent and truthful sales research assistant that analyzes LinkedIn activities of a given prospect to extract useful insights about them.\n"
            "You are given your prospect's name, the company they work for, their current role title, a self-description and the company description.\n"
            "You will also be given a text summarizing recent LinkedIn activities (a post, comment or reaction) associated with your prospect.\n"
            "The text will be delimited by triple quotes.\n"
            "Your job is to answer the user's questions using the information found in the text.\n"
            "\n"
            "**Prospect Details:**\n"
            f"Name: {person_name}\n"
            f"Company: {company_name}\n"
            f"Company Description: {company_description}\n"
            f"Role Title: {person_role_title}\n"
            f"Self Description: {person_about_me}\n"
            "\n"
            ""
        ))

    def generate(self, all_content_details: List[ContentDetails]) -> LeadResearchReport.Insights:
        """Generates insights for given lead and given content details."""

        insights = LeadResearchReport.Insights()
        with get_openai_callback() as cb:

            self.get_personality_traits(
                all_content_details=all_content_details, insights=insights)

            self.get_areas_of_interest(
                all_content_details=all_content_details, insights=insights)

            self.get_engaged_colleagues(
                all_content_details=all_content_details, insights=insights)

            self.get_engaged_products(
                all_content_details=all_content_details, insights=insights)

            insights.total_engaged_activities = len(all_content_details)
            insights.num_company_related_activities = len(
                list(filter(lambda cd: cd.focus_on_company, all_content_details)))

            insights.total_tokens_used = OpenAITokenUsage(operation_tag=self.INSIGHTS_PROCESSING_TAG, prompt_tokens=cb.prompt_tokens,
                                                          completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)

            logger.info(
                f"total processing cost: {insights.total_tokens_used.total_cost_in_usd}")

            logger.info(
                f"Successfully generated Lead Insights from Content in Lead Research Report: {self.lead_research_report_id} and person name: {self.person_name}")

        return insights

    def get_personality_traits(self, all_content_details: List[ContentDetails], insights: LeadResearchReport.Insights):
        """Get personality of the lead using one line summaries from each content."""

        combined_one_line_summaries = "\n\n".join(
            [content_detail.one_line_summary for content_detail in all_content_details])

        question = (
            f"Using information from the summaries of activites above, describe the personality traits of {self.person_name} in one line.\n"
        )
        human_message_prompt_template = (
            '"""{combined_summaries}"""'
            "\n\n"
            f"{question}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.INSIGHT_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class PersonalityTraits(BaseModel):
            description: Optional[str] = Field(
                default=None, description="Description of personality traits.")
            reason: Optional[str] = Field(
                default=None, description="Reason for why these are his attributes.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MINI_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(PersonalityTraits)

        chain = prompt | llm
        result: PersonalityTraits = chain.invoke({
            "combined_summaries": combined_one_line_summaries,
        })

        if result == None:
            logger.error(
                f"Lead Insights: personality result is None from LLM output for Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")
            return

        # Populate lead insights.
        insights.personality_description = result.description

        logger.info(
            f"Lead Insights: Got personality {insights.personality_description} in Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")

    def get_areas_of_interest(self, all_content_details: List[ContentDetails], insights: LeadResearchReport.Insights):
        """Generate Areas of interest of the lead using one line summaries from each content."""

        combined_one_line_summaries = "\n\n".join(
            [content_detail.one_line_summary for content_detail in all_content_details])

        question = (
            f"Using information from the summaries of activites above, desribe the areas of interest of {self.person_name}.\n"
            "Cite the reason for why something is an areas of interest.\n"
        )
        human_message_prompt_template = (
            '"""{combined_summaries}"""'
            "\n\n"
            f"{question}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.INSIGHT_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class AreasOfInterest(BaseModel):
            class Interest(BaseModel):
                description: Optional[str] = Field(
                    default=None, description="Description of Interest.")
                reason: Optional[str] = Field(
                    default=None, description="Reason for why this is an area of interest")
            interests: Optional[List[Interest]] = Field(
                default=None, description="Areas of interests of the lead.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MINI_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(AreasOfInterest)

        chain = prompt | llm
        result: AreasOfInterest = chain.invoke({
            "combined_summaries": combined_one_line_summaries,
        })

        if result == None:
            logger.error(
                f"Lead Insights: areas of interest result is None from LLM output for Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")
            return

        # Populate lead insights.
        insights.areas_of_interest = result

        logger.info(
            f"Lead Insights: Got Areas of interest in Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")

    def get_engaged_colleagues(self, all_content_details: List[ContentDetails], insights: LeadResearchReport.Insights):
        """List of Colleagues most engaged by the lead in their posts."""

        all_engaged_colleagues: List[str] = []
        for content_detail in all_content_details:
            if content_detail.main_colleague == None or content_detail.main_colleague == "":
                continue
            all_engaged_colleagues.append(content_detail.main_colleague)

        if len(all_engaged_colleagues) == 0:
            # No engaged colleagues, nothing to do here.
            return

        engaged_colleagues_combined: str = ",".join(all_engaged_colleagues)

        question = (
            f"The text above has the list of colleagues who {self.person_name} has engaged with in LinkedIn activies.\n"
            f"Using frequencey of occurence, list the most important colleagues of {self.person_name} in the order of most to least important.\n"
        )
        human_message_prompt_template = (
            '"""{engaged_colleagues}"""'
            "\n\n"
            f"{question}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.INSIGHT_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class ImportantColleagues(BaseModel):
            colleagues: Optional[List[str]] = Field(
                default=None, description="List of most important colleagues the lead has engaged with.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MINI_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(ImportantColleagues)

        chain = prompt | llm
        result: ImportantColleagues = chain.invoke({
            "engaged_colleagues": engaged_colleagues_combined,
        })

        if result == None:
            logger.error(
                f"Lead Insights: most important colleagues result is None from LLM output for Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")
            return

        # Populate lead insights.
        insights.engaged_colleagues = result.colleagues

        logger.info(
            f"Lead Insights: most important colleagues {insights.engaged_colleagues} in Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")

    def get_engaged_products(self, all_content_details: List[ContentDetails],  insights: LeadResearchReport.Insights):
        """List of products of company most engaged by the lead in their posts."""

        all_engaged_products: List[str] = []
        for content_detail in all_content_details:
            if content_detail.product_associations == None or len(content_detail.product_associations) == 0:
                continue
            all_engaged_products += content_detail.product_associations

        if len(all_engaged_products) == 0:
            # No engaged colleagues, nothing to do here.
            return

        engaged_products_combined: str = ",".join(all_engaged_products)

        question = (
            f"The text above has the list of products of company {self.company_name} which {self.person_name} has engaged with in LinkedIn activies.\n"
            f"Using frequencey of occurence, list the most important products {self.person_name} has engaged with in the order of most to least important.\n"
        )
        human_message_prompt_template = (
            '"""{engaged_products}"""'
            "\n\n"
            f"{question}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.INSIGHT_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class ImportantProducts(BaseModel):
            products: Optional[List[str]] = Field(
                default=None, description="List of most important products the lead has engaged with.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MINI_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(ImportantProducts)

        chain = prompt | llm
        result: ImportantProducts = chain.invoke({
            "engaged_products": engaged_products_combined,
        })

        if result == None:
            logger.error(
                f"Lead Insights: most important products result is None from LLM output for Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")
            return

        # Populate lead insights.
        insights.engaged_products = result.products

        logger.info(
            f"Lead Insights: most important products {insights.engaged_products} in Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")

    def areas_of_interest_backup(self, all_content_details: List[ContentDetails]):
        """Backup: Generate Areas of interest of the lead using one line summaries from each content."""

        combined_one_line_summaries: str = "\n\n".join(
            [content_detail.one_line_summary for content_detail in all_content_details])

        question = (
            f"Using information from the summaries of activites above, desribe the areas of interest of {self.person_name}.\n"
            "Use bullet points to make it easily readable.\n"
            "Cite the reason for why something is an areas of interest.\n"
        )
        human_message_prompt_template = (
            '"""{combined_summaries}"""'
            "\n\n"
            f"{question}"
        )
        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_message_prompt_template)

        prompt = ChatPromptTemplate.from_messages(
            [
                self.INSIGHT_SYSTEM_MESSAGE,
                human_message_prompt,
            ]
        )

        class AreasOfInterest(BaseModel):
            description: Optional[str] = Field(
                default=None, description="Description of areas of interests of the lead.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MINI_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(AreasOfInterest)

        chain = prompt | llm
        result: AreasOfInterest = chain.invoke({
            "combined_summaries": combined_one_line_summaries,
        })

        if result == None:
            logger.error(
                f"Lead Insights areas of interest result is None from LLM output for Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")
            return

        logger.info(
            f"Got Areas of interest {result.description} in Lead Research Report: {self.lead_research_report_id} for person name: {self.person_name}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    from app.database import Database
    load_dotenv()
    load_dotenv(".env.dev")

    import logging
    logging.basicConfig(level=logging.INFO)

    from datetime import datetime
    from app.utils import Utils
    from dateutil.relativedelta import relativedelta

    database = Database()
    time_now: datetime = Utils.create_utc_time_now()

    lead_research_report_id = "6736c56b71bc3188df5a51d7"

    # Only filter documents from the last 15 months.
    research_report: LeadResearchReport = database.get_lead_research_report(
        lead_research_report_id=lead_research_report_id)

    report_publish_cutoff_date = time_now - relativedelta(months=15)

    pipeline = [
        {
            "$match": {
                "$and": [
                    {"company_profile_id": research_report.company_profile_id},
                    {"person_profile_id": research_report.person_profile_id},
                    {"processing_status": ContentDetails.ProcessingStatus.COMPLETE},
                    {"linkedin_activity_ref_id": {"$ne": None}},
                    {"publish_date": {"$gt": report_publish_cutoff_date}},
                ]
            }
        },
    ]

    results = database.get_content_details_collection().aggregate(pipeline=pipeline)
    all_content_details: List[ContentDetails] = []
    for res in results:
        all_content_details.append(ContentDetails(**res))

    # Get person profile details.
    person_about_me: Optional[str] = database.get_person_profile(
        person_profile_id=research_report.person_profile_id).summary

    import time
    start_time = time.time()

    lead_insights = LeadInsights(lead_research_report_id=lead_research_report_id, person_name=research_report.person_name, company_name=research_report.company_name,
                                 company_description=research_report.company_description, person_role_title=research_report.person_role_title, person_about_me=person_about_me)

    lead_insights.generate(all_content_details=all_content_details)

    logger.info(f"\n\nTotal time taken: {time.time() - start_time} seconds")
