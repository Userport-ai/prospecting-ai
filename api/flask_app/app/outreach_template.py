import os
import logging
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from app.database import Database
from app.models import LeadResearchReport, OutreachEmailTemplate, PersonProfile, OpenAITokenUsage
from app.utils import Utils
from langchain_community.callbacks import get_openai_callback

logger = logging.getLogger()


class OutreachTemplateMatcher:
    """Helps fetch and match Outreach email template for a given lead."""

    OPERATION_TAG_NAME = "choose_outreach_email_template"

    def __init__(self, database: Database) -> None:
        self.database = database
        # Open AI configurations.
        self.OPENAI_API_KEY = os.environ["OPENAI_USERPORT_API_KEY"]
        self.OPENAI_GPT_4O_MODEL = os.environ["OPENAI_GPT_4O_MODEL"]
        self.OPENAI_REQUEST_TIMEOUT_SECONDS = 20
        self.openai_tokens_used: Optional[OpenAITokenUsage] = None

    def match(self, lead_research_report: LeadResearchReport) -> Optional[LeadResearchReport.ChosenOutreachEmailTemplate]:
        """Returns the chosen outreach email template based on the given lead's profile. Returns None if none of the existing email templates matche."""
        user_id: str = lead_research_report.user_id
        person_profile_id: str = lead_research_report.person_profile_id

        email_templates: List[OutreachEmailTemplate] = self.database.list_outreach_email_templates(
            user_id=user_id)
        if len(email_templates) == 0:
            # No existing email templates added by user, we allow this.
            logger.warning(
                f"No existing email templates found for user with ID: {user_id} for report ID: {lead_research_report.id}")
            return None

        person_profile: PersonProfile = self.database.get_person_profile(
            person_profile_id=person_profile_id)
        return self.closest_template(
            email_templates=email_templates, person_profile=person_profile, lead_research_report_id=lead_research_report.id)

    def closest_template(self, email_templates: List[OutreachEmailTemplate], person_profile: PersonProfile, lead_research_report_id: str) -> LeadResearchReport.ChosenOutreachEmailTemplate:
        """Returns the chosen template that most closely matches the lead's profile."""
        person_profile_markdown: str = person_profile.to_markdown()

        prompt_template = (
            "You are an intelligent Sales person who needs to match one of the Persona descriptions below most accurately represents the given Lead's Profile.\n"
            "If none of the Persona descriptions match, then return None. Do not force a match.\n"
            "Each Persona description contains information about that Persona's Role titles and any additional details regarding their skills or experience.\n"
            "Return the matched Persona's ID and reason for why that match makes the most sense.\n"
            "\n"
            "# Lead's LinkedIn Profile\n"
            "{person_profile_markdown}\n"
        )

        for i, template in enumerate(email_templates):
            if i == 0:
                prompt_template += "# Personas List\n\n"
            prompt_template += template.to_persona_description_markdown()

        prompt = PromptTemplate.from_template(prompt_template)

        class MatchedPersona(BaseModel):
            matched_persona_id: Optional[str] = Field(
                default=None, description="ID of the Persona that matched. Set to None if none of the persona's matched.")
            reason: Optional[str] = Field(
                default=None, description="Reason for why a given Persona or None was chosen.")

        llm = ChatOpenAI(temperature=0, model_name=self.OPENAI_GPT_4O_MODEL,
                         api_key=self.OPENAI_API_KEY, timeout=self.OPENAI_REQUEST_TIMEOUT_SECONDS).with_structured_output(MatchedPersona)
        chain = prompt | llm

        result: MatchedPersona = None
        with get_openai_callback() as cb:
            result = chain.invoke(
                {"person_profile_markdown": person_profile_markdown})

            self.openai_tokens_used = OpenAITokenUsage(operation_tag=OutreachTemplateMatcher.OPERATION_TAG_NAME, prompt_tokens=cb.prompt_tokens,
                                                       completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            logger.info(
                f"Total tokens used in Choosing outreach template for report ID: {lead_research_report_id} is: {self.openai_tokens_used}")

        if not result or not result.matched_persona_id or result.matched_persona_id == "None":
            # Sometimes LLMs screw up and set the value to string 'None' instead of Python None.
            logger.warning(
                f"None of the emails templates matched with result: {result} with for Lead with Person profile ID: {person_profile.id} in report ID: {lead_research_report_id}")
            return None

        logger.info(
            f"Chosen template per LLM: {result} for Lead with person profile ID: {person_profile.id} in report ID: {lead_research_report_id}")

        chosen_templates: OutreachEmailTemplate = list(filter(
            lambda template: template.id == result.matched_persona_id, email_templates))
        if len(chosen_templates) != 1:
            raise ValueError(
                f"Expected to find 1 Email template with ID: {result.matched_persona_id}, found: {chosen_templates} for Lead with person profile ID: {person_profile.id} in report: {lead_research_report_id}")
        chosen_email_template: OutreachEmailTemplate = chosen_templates[0]

        return LeadResearchReport.ChosenOutreachEmailTemplate(
            id=result.matched_persona_id,
            name=chosen_email_template.name,
            creation_date=Utils.create_utc_time_now(),
            message=chosen_email_template.message,
        )

    def get_tokens_used(self) -> Optional[OpenAITokenUsage]:
        """Returns tokens used so far in personalization. Can return None if choose outreach template workflow is not run yet."""
        return self.openai_tokens_used

    @ staticmethod
    def from_outreach_template(outreach_email_template: OutreachEmailTemplate) -> LeadResearchReport.ChosenOutreachEmailTemplate:
        """Helper to return Lead report template from given outreach template."""
        return LeadResearchReport.ChosenOutreachEmailTemplate(
            id=outreach_email_template.id,
            name=outreach_email_template.name,
            creation_date=Utils.create_utc_time_now(),
            message=outreach_email_template.message,
        )
