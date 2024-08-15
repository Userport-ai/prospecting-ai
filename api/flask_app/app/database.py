
import os
import contextlib
from typing import Optional, Dict
from itertools import chain
import pymongo
from collections.abc import Generator
from pymongo.mongo_client import MongoClient
from pymongo.client_session import ClientSession
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from pymongo.results import UpdateResult
from bson.objectid import ObjectId
from dotenv import load_dotenv
from datetime import datetime
from app.utils import Utils
from app.models import (
    PersonProfile,
    CompanyProfile,
    ContentDetails,
    LinkedInPost,
    WebPage,
    LeadResearchReport,
    OutreachEmailTemplate,
    OpenAITokenUsage
)
from typing import List

load_dotenv()


class Database:
    """Database class wrapping around MongoDB."""

    MONGODB_CONNECTION_URL = os.getenv("MONGODB_CONNECTION_URI")
    MONGODB_DB_NAME = "userport_db"

    def __init__(self) -> None:
        # Create a new client and connect to the server
        self.mongo_client = MongoClient(
            Database.MONGODB_CONNECTION_URL, server_api=ServerApi('1'))
        self.db = self.mongo_client[Database.MONGODB_DB_NAME]

    @staticmethod
    def _exclude_id() -> List[str]:
        """Helper to exclude ID during model_dump call."""
        return ['id']

    def _get_person_profiles_collection(self) -> Collection:
        """Returns Person Profiles collection."""
        return self.db['person_profiles']

    def _get_company_profiles_collection(self) -> Collection:
        """Returns Company Profiles collection."""
        return self.db['company_profiles']

    def _get_linkedin_posts_collection(self) -> Collection:
        """Returns LinkedIn posts collection."""
        return self.db['linkedin_posts']

    def _get_web_pages_collection(self) -> Collection:
        """Returns Web Page collection."""
        return self.db['web_pages']

    def get_content_details_collection(self) -> Collection:
        """Returns content details collection."""
        return self.db['content_details']

    def _get_lead_research_report_collection(self) -> Collection:
        """Returns Lead Research Report collection."""
        return self.db['lead_research_reports']

    def _get_outreach_email_template_collection(self) -> Collection:
        """Returns Outreach Email Templates collection."""
        return self.db['outreach_email_templates']

    def insert_person_profile(self, person_profile: PersonProfile) -> str:
        """Inserts Person information as a document in the database and returns the created Id."""
        if person_profile.id:
            raise ValueError(
                f"PersonProfile instance cannot have an Id before db insertion: {person_profile}")
        person_profile.creation_date = Utils.create_utc_time_now()

        collection = self._get_person_profiles_collection()
        result = collection.insert_one(
            person_profile.model_dump(exclude=Database._exclude_id()))
        return str(result.inserted_id)

    def insert_company_profile(self, company_profile: CompanyProfile) -> str:
        """Inserts Company information as a document in the database and returns the created Id."""
        if company_profile.id:
            raise ValueError(
                f"CompanyProfile instance cannot have an Id before db insertion: {company_profile}")
        company_profile.creation_date = Utils.create_utc_time_now()

        collection = self._get_company_profiles_collection()
        result = collection.insert_one(
            company_profile.model_dump(exclude=Database._exclude_id()))
        return str(result.inserted_id)

    def insert_linkedin_post(self, linkedin_post: LinkedInPost, session: Optional[ClientSession] = None) -> str:
        """Inserts LinkedIn post information as document in the database and returns the created Id."""
        if linkedin_post.id:
            raise ValueError(
                f"LinkedInPost instance cannot have an Id before db insertion: {linkedin_post}")
        linkedin_post.creation_date = Utils.create_utc_time_now()

        collection = self._get_linkedin_posts_collection()
        result = collection.insert_one(
            linkedin_post.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    def insert_web_page(self, web_page: WebPage, session: Optional[ClientSession] = None) -> str:
        """Inserts web page as document in the database and returns the created Id."""
        if web_page.id:
            raise ValueError(
                f"WebPage instance cannot have an Id before db insertion: {web_page}")
        web_page.creation_date = Utils.create_utc_time_now()

        collection = self._get_web_pages_collection()
        result = collection.insert_one(
            web_page.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    def insert_content_details(self, content_details: ContentDetails, session: Optional[ClientSession] = None) -> str:
        """Inserts ContentInfo in the database and returns the created Id."""
        if content_details.id:
            raise ValueError(
                f"Content Details instance cannot have an Id before db insertion: {content_details}")
        content_details.creation_date = Utils.create_utc_time_now()

        collection = self.get_content_details_collection()
        result = collection.insert_one(
            content_details.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    def insert_lead_research_report(self, lead_research_report: LeadResearchReport, session: Optional[ClientSession] = None) -> str:
        """Inserts Lead Research Report in the database and returns the created Id."""
        if lead_research_report.id:
            raise ValueError(
                f"Lead Research report instance cannot have an Id before db insertion: {lead_research_report}")
        lead_research_report.creation_date = Utils.create_utc_time_now()

        collection = self._get_lead_research_report_collection()
        result = collection.insert_one(
            lead_research_report.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    def insert_outreach_email_template(self, outreach_email_template: OutreachEmailTemplate, session: Optional[ClientSession] = None) -> str:
        """Inserts Outreach Email template in the database and returns the created Id."""
        if outreach_email_template.id:
            raise ValueError(
                f"Outreach Email Template instance cannot have an Id before db insertion: {outreach_email_template}")
        current_time: datetime = Utils.create_utc_time_now()
        current_time_readable_str: str = Utils.to_human_readable_date_str(
            current_time)
        outreach_email_template.creation_date = current_time
        outreach_email_template.creation_date_readable_str = current_time_readable_str
        outreach_email_template.last_updated_date = current_time
        outreach_email_template.last_updated_date_readable_str = current_time_readable_str

        collection = self._get_outreach_email_template_collection()
        result = collection.insert_one(
            outreach_email_template.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    def get_db_ready_personalized_emails(self, personalized_emails: List[LeadResearchReport.PersonalizedEmail]) -> List[Dict]:
        """Returns a personalized email list of dictionaries from given input meail list that is populated and ready to be inserted in the database."""
        creation_date: datetime = Utils.create_utc_time_now()
        creation_date_readable_str: str = Utils.to_human_readable_date_str(
            creation_date)
        last_updated_date = creation_date
        last_updated_date_readable_str = creation_date_readable_str

        for email in personalized_emails:
            email.creation_date = creation_date
            email.creation_date_readable_str = creation_date_readable_str
            email.last_updated_date = last_updated_date
            email.last_updated_date_readable_str = last_updated_date_readable_str

        # Convert to list of Python dictionaries and insert ObjectIds manually.
        personalized_emails_dict_list: List[Dict] = [email.model_dump(
            exclude=Database._exclude_id()) for email in personalized_emails]
        for email_dict in personalized_emails_dict_list:
            email_dict["_id"] = ObjectId()

        return personalized_emails_dict_list

    @contextlib.contextmanager
    def transaction_session(self) -> Generator[ClientSession, None]:
        """Wrapper Context manager around MongoDB client session to skip creating a new instance method for each new type of transacation.

        Example:
        with self.database.transaction_session() as session:
            self.database.insert_linkedin_post(post, session=session)
            self.database.insert_web_search_resul(result, session=session)
        """
        with self.mongo_client.start_session() as session:
            with session.start_transaction():
                yield session

    def get_person_profile(self, person_profile_id: str) -> PersonProfile:
        """Returns person profile for given ID."""
        collection = self._get_person_profiles_collection()
        data_dict = collection.find_one({"_id": ObjectId(person_profile_id)})
        if not data_dict:
            raise ValueError(
                f'Person profile not found for Id: {person_profile_id}')
        return PersonProfile(**data_dict)

    def get_person_profile_by_url(self, person_linkedin_url: str) -> Optional[PersonProfile]:
        """Returns person profile for given person's LinkedIn URL. Returns None if no profile exists for given URL."""
        collection = self._get_person_profiles_collection()
        data_dict = collection.find_one({"linkedin_url": person_linkedin_url})
        if not data_dict:
            return None
        return PersonProfile(**data_dict)

    def get_company_profile_by_url(self, company_linkedin_url: str) -> Optional[CompanyProfile]:
        """Returns company profile for given company's LinkedIn URL. Returns None if no company profile exists for given URL."""
        collection = self._get_company_profiles_collection()
        data_dict = collection.find_one({"linkedin_url": company_linkedin_url})
        if not data_dict:
            return None
        return CompanyProfile(**data_dict)

    def get_content_details_by_url(self, url: str) -> Optional[ContentDetails]:
        """Returns Content details for given url. Returns None if not found."""
        collection = self.get_content_details_collection()
        data_dict = collection.find_one({"url": url})
        if not data_dict:
            return None
        return ContentDetails(**data_dict)

    def get_content_details(self, content_details_id: str) -> Optional[ContentDetails]:
        """Returns Content details for given ID."""
        collection = self.get_content_details_collection()
        data_dict = collection.find_one({"_id": ObjectId(content_details_id)})
        if not data_dict:
            raise ValueError(
                f'Content Details not found for Id: {content_details_id}')
        return ContentDetails(**data_dict)

    def get_lead_research_report(self, lead_research_report_id: str, projection: Optional[Dict[str, int]] = None) -> LeadResearchReport:
        """Returns Lead Research report for given Report ID."""
        collection = self._get_lead_research_report_collection()
        data_dict = collection.find_one(
            {"_id": ObjectId(lead_research_report_id)}, projection=projection)
        if not data_dict:
            raise ValueError(
                f'Lead Research report not found for Id: {lead_research_report_id}')
        return LeadResearchReport(**data_dict)

    def get_lead_research_report_by_url(self, user_id: str, person_linkedin_url: str) -> Optional[LeadResearchReport]:
        """Returns Lead Research report for given person's LinkedIn URL and the user who created the report. If it doesn't exist, returns None."""
        collection = self._get_lead_research_report_collection()
        data_dict = collection.find_one(
            {"user_id": user_id, "person_linkedin_url": person_linkedin_url})
        if not data_dict:
            return None
        return LeadResearchReport(**data_dict)

    def get_outreach_email_template(self, outreach_email_template_id: str, projection: Optional[Dict[str, int]] = None) -> OutreachEmailTemplate:
        """Returns Outreach Email Template for given Template ID."""
        collection = self._get_outreach_email_template_collection()
        data_dict = collection.find_one(
            {"_id": ObjectId(outreach_email_template_id)}, projection=projection)
        if not data_dict:
            raise ValueError(
                f'Outreach Email Template not found for Id: {outreach_email_template_id}')
        return OutreachEmailTemplate(**data_dict)

    def list_lead_research_reports(self, user_id: str, projection: Optional[Dict[str, int]] = None) -> List[LeadResearchReport]:
        """Returns Lead Research reports created by given user. Returns only fields specified in the projection dictionary."""
        collection = self._get_lead_research_report_collection()
        # TODO: Update filter to pass in user and organization as fields to filter on.
        # TODO: Add pagination using skip() as well.
        cursor = collection.find({"user_id": user_id}, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        lead_research_reports: List[LeadResearchReport] = []
        for research_report_dict in cursor:
            lead_research_reports.append(
                LeadResearchReport(**research_report_dict))
        return lead_research_reports

    def list_outreach_email_templates(self, user_id: str, projection: Optional[Dict[str, int]] = None) -> List[OutreachEmailTemplate]:
        """Returns Outreach Emails created by given user. Returns only fields specified in the projection dictionary."""
        collection = self._get_outreach_email_template_collection()
        cursor = collection.find({"user_id": user_id}, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        outreach_email_templates: List[OutreachEmailTemplate] = []
        for outreach_email_template_dict in cursor:
            outreach_email_templates.append(
                OutreachEmailTemplate(**outreach_email_template_dict))
        return outreach_email_templates

    def update_lead_research_report(self, lead_research_report_id: str, setFields: Dict[str, str]):
        """Sets fields for given Lead Research Report ID. Assumes that fields are existing fields in the LeadResearchReport Document model."""
        collection = self._get_lead_research_report_collection()
        if "last_updated_date" not in setFields:
            setFields["last_updated_date"] = Utils.create_utc_time_now()

        res: UpdateResult = collection.update_one(
            {"_id": ObjectId(lead_research_report_id)}, {"$set": setFields})
        if res.matched_count == 0:
            raise ValueError(
                f"Could not update research report with ID: {lead_research_report_id}")

    def delete_outreach_email_templates(self, outreach_email_template_id: str):
        """Deletes outreach email template with given ID."""
        collection = self._get_outreach_email_template_collection()
        result = collection.delete_one(
            {"_id": ObjectId(outreach_email_template_id)})
        if result.deleted_count != 1:
            raise ValueError(
                f"Failed to delete document with ID: {outreach_email_template_id}, deleted {result.deleted_count} docs.")

    def delete_all_content_details(self):
        """Deletes all content details and associated web pages and LinkedIn posts."""
        content_collection = self.get_content_details_collection()

        content_ids = []
        linkedin_ids = []
        web_page_ids = []
        cursor = content_collection.find({})
        for content_detail in cursor:
            content_ids.append(content_detail['_id'])
            linkedin_ids.append(content_detail['linkedin_post_ref_id'])
            web_page_ids.append(content_detail['web_page_ref_id'])

        post_collection = self._get_linkedin_posts_collection()
        post_collection.delete_many(
            {'_id': {'$in': [ObjectId(lid) for lid in linkedin_ids]}})

        web_pages_collection = self._get_web_pages_collection()
        web_pages_collection.delete_many(
            {'_id': {'$in': [ObjectId(lid) for lid in web_page_ids]}})

        content_collection.delete_many({'_id': {'$in': content_ids}})

    def migrate_docs(self, collection: Collection, filter: Dict, update: Dict):
        """Internal method to migrate many documents in given collection with given updates.

        DO NOT USE in production code.
        """
        collection.update_many(filter=filter, update=update)

    def _test_connection(self):
        """Helper method to test successful connection to cluster deployment."""
        try:
            self.mongo_client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB wohoo!")
        except Exception as e:
            print(e)


if __name__ == "__main__":

    db = Database()
    # content_details_id = '66a88a0fa052ee77579340a0'
    # details = db.get_content_details(content_details_id=content_details_id)

    # db.delete_all_content_details()

    # Migration script.
    # update = {
    #     "$set": {
    #         "personalized_emails.$.highlight_id": "66a8e6adbc8a1e4270c9b29f",
    #     }
    # }

    # db.migrate_docs(
    #     collection=db._get_lead_research_report_collection(), filter={"personalized_emails._id": ObjectId("66baecd4914935040bcf629d")}, update=update)
    print("done")

    # db.insert_personalized_emails(lead_research_report_id="", personalized_emails=[
    #     LeadResearchReport.PersonalizedEmail(id=None, email_opener="hello"),
    #     LeadResearchReport.PersonalizedEmail(id=None, email_opener="world"),
    #     LeadResearchReport.PersonalizedEmail(id=None, email_opener="userport"),
    # ])
