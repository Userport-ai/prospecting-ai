from database import Database
from utils import Utils
from datetime import datetime
from dateutil.relativedelta import relativedelta
from models import LeadResearchReport


class ResearchReport:
    """Helper to create a research report for given person in a company from all relevant data in the database."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, person_profile_id: str, company_profile_id: str) -> LeadResearchReport:
        """Creates and returns Research report for given Person and Company."""
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

        results = self.database.get_content_details_collection().aggregate(pipeline=pipeline)

        research_report = LeadResearchReport(cutoff_publish_date=latest_publish_date, person_profile_id=person_profile_id,
                                             company_profile_id=company_profile_id, details=[])

        for detail in results:
            report_detail = LeadResearchReport.ReportDetail(**detail)
            research_report.details.append(report_detail)

        for detail in research_report.details:
            print("Category: ", detail.category)
            print("Num highlights: ", len(detail.highlights))
            import pprint
            pprint.pprint(detail.highlights)
            print("---------------------")
            print("\n")

        print("cutoff publish date: ", research_report.cutoff_publish_date)
        return research_report


if __name__ == "__main__":
    # Zach perret Profile ID.
    person_profile_id = '66a70cc8ff3944ed08fe4f1c'
    company_profile_id = '66a7a6b5066fac22c378bd75'

    rp = ResearchReport(database=Database())
    rp.create(person_profile_id=person_profile_id,
              company_profile_id=company_profile_id)
