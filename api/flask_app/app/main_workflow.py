from typing import Optional
from pydantic import BaseModel, Field
from database import Database
from models import PersonProfile, CompanyProfile
from linkedin_scraper import LinkedInScraper


class MainWorkflow:
    """This workflow is run in the live path of the API request to fetch all information for a given person.

    It does a small amount of amount:
    1. Fetch person's profile from database and if it doesn't exist, creates it.
    2. Fetch person's current company's profile from database and if it doesn't exist, creates it.

    The rest of the work in gathering information about the lead or company is 
    """

    class Result(BaseModel):
        person_profile_id: Optional[str] = Field(
            default=None, description="Identifier of Person Profile in the database.")
        company_profile_id: Optional[str] = Field(
            default=None, description="Identifier of Company Profile in the database.")

    def __init__(self, database: Database) -> None:
        self.database = database

    def run(self, person_linkedin_url: str) -> Result:
        """Takes LinkedIn URL of the person and fetches person's profile and company's profile identifiers from the database."""
        result = MainWorkflow.Result()

        # Compute person profile ID.
        person_profile: Optional[PersonProfile] = self.database.get_person_profile_by_url(
            person_linkedin_url=person_linkedin_url)
        if not person_profile:
            print(
                f"Person {person_linkedin_url} profile NOT found in database.")
            person_profile = LinkedInScraper.fetch_person_profile(
                profile_url=person_linkedin_url)
            result.person_profile_id = self.database.insert_person_profile(
                person_profile=person_profile)
        else:
            print(
                f"Person {person_linkedin_url} profile found in database.")
            result.person_profile_id = person_profile.id

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
            result.company_profile_id = self.database.insert_company_profile(
                company_profile=company_profile)
        else:
            print(
                f"Company {company_linkedin_url} profile found in database.")
            result.company_profile_id = company_profile.id

        return result


if __name__ == "__main__":
    person_url = "https://www.linkedin.com/in/zperret"
    db = Database()
    mw = MainWorkflow(database=db)
    result = mw.run(person_linkedin_url=person_url)
    print("result: ", result)
