import os
import logging
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from app.database import Database
from app.models import LeadResearchReport, OutreachEmailTemplate, PersonProfile
from app.utils import Utils

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger()


class OutreachTemplateMatcher:
    """Helps fetch and match Outreach email template for a given lead."""

    # Open AI configurations.
    OPENAI_API_KEY = os.getenv("OPENAI_USERPORT_API_KEY")
    OPENAI_GPT_4O_MODEL = os.getenv("OPENAI_GPT_4O_MODEL")

    def __init__(self, database: Database) -> None:
        self.database = database

    def match(self, lead_research_report_id: str) -> LeadResearchReport.ChosenOutreachEmailTemplate:
        """Matches and returns the chosen outreach email template for given lead."""
        lead_research_report: LeadResearchReport = self.database.get_lead_research_report(
            lead_research_report_id=lead_research_report_id)
        if lead_research_report.status != LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE:
            raise ValueError(
                f"Expected report status to be: {LeadResearchReport.Status.RECENT_NEWS_AGGREGATION_COMPLETE}, got: {lead_research_report.status}")
        user_id: str = lead_research_report.user_id
        person_profile_id: str = lead_research_report.person_profile_id

        email_templates: List[OutreachEmailTemplate] = self.database.list_outreach_email_templates(
            user_id=user_id)
        if len(email_templates) == 0:
            # No existing email templates added by user.
            error_message = f"Failed to find closest email template: No existing email templates found for User with ID: {user_id}"
            logger.exception(error_message)
            raise ValueError(error_message)

        person_profile: PersonProfile = self.database.get_person_profile(
            person_profile_id=person_profile_id)
        return self.closest_template(
            email_templates=email_templates, person_profile=person_profile)

    def closest_template(self, email_templates: List[OutreachEmailTemplate], person_profile: PersonProfile) -> LeadResearchReport.ChosenOutreachEmailTemplate:
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

        llm = ChatOpenAI(temperature=0, model_name=OutreachTemplateMatcher.OPENAI_GPT_4O_MODEL,
                         api_key=OutreachTemplateMatcher.OPENAI_API_KEY).with_structured_output(MatchedPersona)
        chain = prompt | llm
        result: MatchedPersona = chain.invoke(
            {"person_profile_markdown": person_profile_markdown})
        if not result.matched_persona_id:
            logger.warning(
                f"None of the emails templates matched with for Person profile ID: {person_profile.id} for user ID: {email_templates[0].user_id}")
            return LeadResearchReport.ChosenOutreachEmailTemplate(id=None, reason=result.reason, message=None, creation_date=Utils.create_utc_time_now())

        logger.info(f"Chosen template per LLM: {result}")

        chosen_templates: OutreachEmailTemplate = list(filter(
            lambda template: template.id == result.matched_persona_id, email_templates))
        if len(chosen_templates) != 1:
            raise ValueError(
                f"Expected to find 1 Email template with ID: {result.matched_persona_id}, found: {chosen_templates}")
        chosen_email_template: OutreachEmailTemplate = chosen_templates[0]

        return LeadResearchReport.ChosenOutreachEmailTemplate(
            id=result.matched_persona_id,
            name=chosen_email_template.name,
            creation_date=Utils.create_utc_time_now(),
            message=chosen_email_template.message,
            reason=result.reason,
        )

    @staticmethod
    def from_outreach_template(outreach_email_template: OutreachEmailTemplate) -> LeadResearchReport.ChosenOutreachEmailTemplate:
        """Helper to return Lead report template from given outreach template."""
        return LeadResearchReport.ChosenOutreachEmailTemplate(
            id=outreach_email_template.id,
            name=outreach_email_template.name,
            creation_date=Utils.create_utc_time_now(),
            message=outreach_email_template.message,
            reason="Manual Selection by user.",
        )


if __name__ == "__main__":
    matcher = OutreachTemplateMatcher(database=Database())
    result = matcher.match(lead_research_report_id="66ab9633a3bb9048bc1a0be5")
    logger.info(f"\n Chosen template result: {result}")
