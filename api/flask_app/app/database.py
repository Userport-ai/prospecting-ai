
import os
import logging
import contextlib
from typing import Optional, Dict
import pymongo
from collections.abc import Generator
from pymongo.mongo_client import MongoClient
from pymongo.client_session import ClientSession
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from pymongo.results import UpdateResult
from bson.objectid import ObjectId
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
    User,
    UsageTier
)
from typing import List

logger = logging.getLogger()


class Database:
    """Database class wrapping around MongoDB."""
    MONGODB_DB_NAME = "userport_db"

    def __init__(self) -> None:
        # Create a new client and connect to the server
        self.mongo_client = MongoClient(
            os.environ["MONGODB_CONNECTION_URI"], server_api=ServerApi('1'))
        self.db = self.mongo_client[Database.MONGODB_DB_NAME]

    @ staticmethod
    def _exclude_id() -> List[str]:
        """Helper to exclude ID during model_dump call."""
        return ['id']

    def _get_users_collection(self) -> Collection:
        """Returns Users collection."""
        return self.db['users']

    def _get_person_profiles_collection(self) -> Collection:
        """Returns Person Profiles collection."""
        return self.db['person_profiles']

    def _get_company_profiles_collection(self) -> Collection:
        """Returns Company Profiles collection."""
        return self.db['company_profiles']

    def get_linkedin_posts_collection(self) -> Collection:
        """Returns LinkedIn posts collection."""
        return self.db['linkedin_posts']

    def get_web_pages_collection(self) -> Collection:
        """Returns Web Page collection."""
        return self.db['web_pages']

    def get_content_details_collection(self) -> Collection:
        """Returns content details collection."""
        return self.db['content_details']

    def get_lead_research_report_collection(self) -> Collection:
        """Returns Lead Research Report collection."""
        return self.db['lead_research_reports']

    def get_outreach_email_template_collection(self) -> Collection:
        """Returns Outreach Email Templates collection."""
        return self.db['outreach_email_templates']

    def create_new_user(self, user_id: str, email: str) -> User:
        """Creates a new user in the database and returns created user object.

        Private method, should not be called by external clients.
        """
        user = User(_id=user_id, state=User.State.NEW_USER, email=email)
        creation_date: datetime = Utils.create_utc_time_now()
        user.creation_date = creation_date
        user.last_updated_date = creation_date
        # By default, we assign a new user a free tier.
        user.usage_tier = UsageTier.FREE

        collection = self._get_users_collection()
        collection.insert_one(user.model_dump(by_alias=True))
        return user

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

        collection = self.get_linkedin_posts_collection()
        result = collection.insert_one(
            linkedin_post.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    def insert_web_page(self, web_page: WebPage, session: Optional[ClientSession] = None) -> str:
        """Inserts web page as document in the database and returns the created Id."""
        if web_page.id:
            raise ValueError(
                f"WebPage instance cannot have an Id before db insertion: {web_page}")
        web_page.creation_date = Utils.create_utc_time_now()

        collection = self.get_web_pages_collection()
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

        collection = self.get_lead_research_report_collection()
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

        collection = self.get_outreach_email_template_collection()
        result = collection.insert_one(
            outreach_email_template.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

    @ contextlib.contextmanager
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

    def get_user(self, user_id: str, projection: Optional[Dict[str, int]] = None) -> Optional[User]:
        """Returns User for given ID. If the user does not exist, returns None."""
        collection = self._get_users_collection()
        data_dict = collection.find_one(
            {"_id": user_id}, projection=projection)
        if not data_dict:
            return None
        return User(**data_dict)

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

    def get_content_details_by_url(self, url: str, company_profile_id: str, processing_status: ContentDetails.ProcessingStatus) -> Optional[ContentDetails]:
        """Returns Content details for given url and company profile and given processing status. Returns None if not found."""
        collection = self.get_content_details_collection()
        data_dict = collection.find_one(
            {"url": url, "company_profile_id": company_profile_id, "processing_status": processing_status.value})
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

    def list_users(self, filter: Dict, projection: Optional[Dict[str, int]] = None) -> List[User]:
        """List users for given filter and projection. It will be """
        collection = self._get_users_collection()
        cursor = collection.find(filter, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        users: List[User] = []
        for user_dict in cursor:
            users.append(User(**user_dict))
        return users

    def list_content_details(self, filter: Dict, projection: Optional[Dict[str, int]] = None) -> List[ContentDetails]:
        """Returns Content Details with given filter. Returns only fields specified in the projection dictionary."""
        collection = self.get_content_details_collection()
        cursor = collection.find(filter, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        content_details_list: List[ContentDetails] = []
        for content_details_dict in cursor:
            content_details_list.append(
                ContentDetails(**content_details_dict))
        return content_details_list

    def get_lead_research_report(self, lead_research_report_id: str, projection: Optional[Dict[str, int]] = None) -> LeadResearchReport:
        """Returns Lead Research report for given Report ID. Raises error if report is not found in the database."""
        collection = self.get_lead_research_report_collection()
        data_dict = collection.find_one(
            {"_id": ObjectId(lead_research_report_id)}, projection=projection)
        if not data_dict:
            raise ValueError(
                f'Lead Research report not found for Id: {lead_research_report_id}')
        return LeadResearchReport(**data_dict)

    def get_lead_research_report_by_url(self, user_id: str, person_linkedin_url: str,  projection: Optional[Dict[str, int]] = None) -> Optional[LeadResearchReport]:
        """Returns Lead Research report for given person's LinkedIn URL and the user who created the report. If it doesn't exist, returns None."""
        collection = self.get_lead_research_report_collection()
        data_dict = collection.find_one(
            {"user_id": user_id, "person_linkedin_url": person_linkedin_url}, projection=projection)
        if not data_dict:
            return None
        return LeadResearchReport(**data_dict)

    def list_lead_research_reports(self, filter: Dict, projection: Optional[Dict[str, int]] = None) -> List[LeadResearchReport]:
        """Returns Lead Research reports with given filter. Returns only fields specified in the projection dictionary."""
        collection = self.get_lead_research_report_collection()
        # TODO: Add pagination using skip() as well.
        cursor = collection.find(filter, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        lead_research_reports: List[LeadResearchReport] = []
        for research_report_dict in cursor:
            lead_research_reports.append(
                LeadResearchReport(**research_report_dict))
        return lead_research_reports

    def list_raw_lead_research_reports(self, filter: Dict, projection: Optional[Dict[str, int]] = None) -> List[LeadResearchReport]:
        """Returns a list of python dictionaries of Lead Research reports with given filter. Should only be used for migration use cases."""
        collection = self.get_lead_research_report_collection()
        # TODO: Add pagination using skip() as well.
        cursor = collection.find(filter, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        results: List[Dict] = []
        for research_report_dict in cursor:
            results.append(research_report_dict)
        return results

    def get_outreach_email_template(self, outreach_email_template_id: str, projection: Optional[Dict[str, int]] = None) -> OutreachEmailTemplate:
        """Returns Outreach Email Template for given Template ID."""
        collection = self.get_outreach_email_template_collection()
        data_dict = collection.find_one(
            {"_id": ObjectId(outreach_email_template_id)}, projection=projection)
        if not data_dict:
            raise ValueError(
                f'Outreach Email Template not found for Id: {outreach_email_template_id}')
        return OutreachEmailTemplate(**data_dict)

    def list_outreach_email_templates(self, user_id: str, projection: Optional[Dict[str, int]] = None) -> List[OutreachEmailTemplate]:
        """Returns Outreach Emails created by given user. Returns only fields specified in the projection dictionary."""
        collection = self.get_outreach_email_template_collection()
        cursor = collection.find({"user_id": user_id}, projection).sort(
            [('creation_date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]
        )
        outreach_email_templates: List[OutreachEmailTemplate] = []
        for outreach_email_template_dict in cursor:
            outreach_email_templates.append(
                OutreachEmailTemplate(**outreach_email_template_dict))
        return outreach_email_templates

    def update_user(self, user_id: str, setFields: Dict[str, str]):
        """Updates fields for given User object. Assumes that fields are existing fields in the User Document model."""
        collection = self._get_users_collection()
        if "last_updated_date" not in setFields:
            setFields["last_updated_date"] = Utils.create_utc_time_now()

        res: UpdateResult = collection.update_one(
            {"_id": user_id}, {"$set": setFields})
        if res.matched_count == 0:
            raise ValueError(
                f"Could not update User with ID: {user_id} in the database.")

    def update_lead_research_report(self, lead_research_report_id: str, setFields: Dict[str, str]):
        """Updates fields for given Lead Research Report ID. Assumes that fields are existing fields in the LeadResearchReport Document model."""
        collection = self.get_lead_research_report_collection()
        if "last_updated_date" not in setFields:
            setFields["last_updated_date"] = Utils.create_utc_time_now()

        res: UpdateResult = collection.update_one(
            {"_id": ObjectId(lead_research_report_id)}, {"$set": setFields})
        if res.matched_count == 0:
            raise ValueError(
                f"Could not update research report with ID: {lead_research_report_id}")

    def update_outreach_email_template(self, outreach_email_template_id: str, setFields: Dict[str, str]):
        """Updates fields for given Outreach Email Template ID. Assumes that fields are existing fields in the OutreachEmailTemplate Document model."""
        collection = self.get_outreach_email_template_collection()
        if "last_updated_date" not in setFields:
            time_now: datetime = Utils.create_utc_time_now()
            setFields["last_updated_date"] = time_now
            setFields["last_updated_date_readable_str"] = Utils.to_human_readable_date_str(
                time_now)

        res: UpdateResult = collection.update_one(
            {"_id": ObjectId(outreach_email_template_id)}, {"$set": setFields})
        if res.matched_count == 0:
            raise ValueError(
                f"Could not update outreach email template with ID: {outreach_email_template_id}")

    def delete_outreach_email_templates(self, outreach_email_template_id: str):
        """Deletes outreach email template with given ID."""
        collection = self.get_outreach_email_template_collection()
        result = collection.delete_one(
            {"_id": ObjectId(outreach_email_template_id)})
        if result.deleted_count != 1:
            raise ValueError(
                f"Failed to delete document with ID: {outreach_email_template_id}, deleted {result.deleted_count} docs.")

    def delete_one_object_id(self, collection: Collection, id_to_delete: str):
        """Deletes given Object ID from given collection. If 1 doc is not deleted, an error is thrown."""
        result = collection.delete_one(
            {"_id": ObjectId(id_to_delete)})
        if result.deleted_count != 0 and result.deleted_count != 1:
            raise ValueError(
                f"Expected to delete 1 doc with ID: {id_to_delete} in collection: {collection.name}, deleted {result.deleted_count} docs.")

    def delete_object_ids(self, collection: Collection, ids_to_delete: List[str]):
        """Deletes given list of object IDs from given collection. If the exact number is not deleted, an error is thrown."""
        if len(ids_to_delete) == 0:
            return
        result = collection.delete_many(
            filter={"_id": {"$in": [ObjectId(id) for id in ids_to_delete]}})
        if result.deleted_count != 0 and result.deleted_count != len(ids_to_delete):
            raise ValueError(
                f"Expected to delete {len(ids_to_delete)} docs in collection: {collection.name} namely: {ids_to_delete}: but deleted only {result.deleted_count} docs.")

    def delete_all_content_details(self, find_filter: Dict, delete_confirm: bool = False):
        """Deletes all content details and associated web pages and LinkedIn posts."""
        if find_filter == {}:
            raise ValueError("Find filter cannot be empty dictionary!")

        content_collection = self.get_content_details_collection()

        content_ids = []
        linkedin_ids = []
        web_page_ids = []
        cursor = content_collection.find(find_filter)
        for content_detail in cursor:
            content_ids.append(content_detail['_id'])
            if content_detail['linkedin_post_ref_id']:
                linkedin_ids.append(content_detail['linkedin_post_ref_id'])
            if content_detail['web_page_ref_id']:
                web_page_ids.append(content_detail['web_page_ref_id'])

        print(
            f"Will be deleting {len(linkedin_ids)} linkedin posts and {len(web_page_ids)} web page references and content posts: {len(content_ids)}")

        if not delete_confirm:
            raise ValueError(
                "Cannot delete content without delete_confirm permission")

        if len(linkedin_ids):
            self.get_linkedin_posts_collection().delete_many(
                {'_id': {'$in': [ObjectId(lid) for lid in linkedin_ids]}})

        if len(web_page_ids):
            self.get_web_pages_collection().delete_many(
                {'_id': {'$in': [ObjectId(lid) for lid in web_page_ids]}})

        if len(content_ids):
            content_collection.delete_many({'_id': {'$in': content_ids}})
        print("Deletion complete")

    def migrate_docs(self, collection: Collection, filter: Dict, update: Dict):
        """Internal method to migrate many documents in given collection with given updates.

        DO NOT USE in production code.
        """
        collection.update_many(filter=filter, update=update)

    def test_connection(self):
        """Helper method to test successful connection to cluster deployment."""
        self.mongo_client.admin.command('ping')


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.dev")

    db = Database()
    # content_details_id = '66a88a0fa052ee77579340a0'
    # details = db.get_content_details(content_details_id=content_details_id)

    # db.delete_all_content_details()

    delete_filter = {
        "creation_date": {"$gte": Utils.create_utc_datetime(5, 9, 2024)}
    }
    db.delete_all_content_details(
        find_filter=delete_filter, delete_confirm=False)

    # collection = db.get_lead_research_report_collection()
    # data_dict = collection.find_one(
    #     {"_id": ObjectId("66e03823aa3050fa413d4244")}, projection=None)
    # got_list = data_dict["personalized_outreach_messages"]["personalized_emails"]["personalized_emails"][0]

    # import pprint
    # pprint.pprint(got_list, indent=4)

    # setFields = {
    #     "personalized_outreach_messages.personalized_emails": got_list,
    # }
    # collection.update_one(
    #     {"_id": ObjectId("66e03823aa3050fa413d4244")}, {"$set": setFields})
