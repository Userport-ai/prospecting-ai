from typing import Optional, List
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.utils import Utils
from app.models import LeadResearchReport, PersonProfile, CompanyProfile
from app.database import Database
from app.linkedin_scraper import LinkedInScraper


class ResearchReport:
    """Helper to create a research report for given person in a company from all relevant data in the database."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, person_linkedin_url: str) -> str:
        """Creates Research report in the database for given lead's LinkedIn URL and returns the created ID."""
        lead_research_report = LeadResearchReport()

        # Compute person profile ID.
        person_profile: Optional[PersonProfile] = self.database.get_person_profile_by_url(
            person_linkedin_url=person_linkedin_url)
        if not person_profile:
            print(
                f"Person LinkedIn profile: {person_linkedin_url} NOT found in database.")
            person_profile = LinkedInScraper.fetch_person_profile(
                profile_url=person_linkedin_url)
            lead_research_report.person_profile_id = self.database.insert_person_profile(
                person_profile=person_profile)
        else:
            print(
                f"Person LinkedIn profile: {person_linkedin_url} profile found in database.")
            lead_research_report.person_profile_id = person_profile.id

        # Compute company profile ID.
        company_name, _ = person_profile.get_company_and_role_title()
        company_linkedin_url = person_profile.get_company_linkedin_url(
            company_name=company_name)
        company_profile: Optional[CompanyProfile] = self.database.get_company_profile_by_url(
            company_linkedin_url=company_linkedin_url)
        if not company_profile:
            print(
                f"Company {company_linkedin_url} profile NOT found in database.")
            company_profile = LinkedInScraper.fetch_company_profile(
                profile_url=company_linkedin_url)
            lead_research_report.company_profile_id = self.database.insert_company_profile(
                company_profile=company_profile)
        else:
            print(
                f"Company {company_linkedin_url} profile found in database.")
            lead_research_report.company_profile_id = company_profile.id

        # Add to database.
        lead_research_report.person_linkedin_url = person_linkedin_url
        lead_research_report.status = LeadResearchReport.Status.IN_PROGRESS
        return self.database.insert_lead_research_report(
            lead_research_report=lead_research_report)

    def update_details(self, lead_research_report_id: str):
        """Fetches Details of research report for given Person and Company and updates them in the database."""
        time_now: datetime = Utils.create_utc_time_now()

        # Only filter documents from recent months.
        latest_publish_date = time_now - relativedelta(months=12)

        stage_match_person_and_company = {
            "$match": {
                "person_profile_id": person_profile_id,
                "company_profile_id": company_profile_id,
            }
        }

        stage_match_publish_date = {
            "$match": {
                "publish_date": {"$gt": latest_publish_date}
            }
        }

        stage_match_category = {
            "$match": {
                "category": {"$ne": "none_of_the_above"}
            }
        }

        stage_match_not_requesting_contact_info = {
            "$match": {
                "requesting_user_contact": {"$eq": False}
            }
        }

        stage_project_fields = {
            "$project": {
                "_id": 1,
                "url": 1,
                "publish_date": 1,
                "concise_summary": 1,
                "category": 1,
            }
        }

        stage_group_by_category = {
            "$group": {
                "_id": "$category",
                "highlights": {"$push": "$$ROOT"}
            }
        }

        stage_final_projection = {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "highlights": 1,
            }
        }

        pipeline = [
            stage_match_person_and_company,
            stage_match_publish_date,
            stage_match_category,
            stage_match_not_requesting_contact_info,
            stage_project_fields,
            stage_group_by_category,
            stage_final_projection
        ]

        report_details: List[LeadResearchReport.ReportDetail] = []
        results = self.database.get_content_details_collection().aggregate(pipeline=pipeline)
        for detail in results:
            rep_detail = LeadResearchReport.ReportDetail(**detail)
            report_details.append(rep_detail)

        for detail in report_details:
            print("Category: ", detail.category)
            print("Num highlights: ", len(detail.highlights))
            import pprint
            pprint.pprint(detail.highlights)
            print("---------------------")
            print("\n")

        setFields = {
            "status": LeadResearchReport.Status.COMPLETE,
            "cutoff_publish_date": latest_publish_date,
            "details": report_details,
        }
        self.database.update_lead_research_report(
            lead_research_report_id=lead_research_report_id, setFields=setFields)


if __name__ == "__main__":
    # Zach perret Profile ID.
    person_url = "https://www.linkedin.com/in/zperret"
    person_profile_id = '66a70cc8ff3944ed08fe4f1c'
    company_profile_id = '66a7a6b5066fac22c378bd75'

    rp = ResearchReport(database=Database())
    rp.fetch(person_profile_id=person_profile_id,
             company_profile_id=company_profile_id)
