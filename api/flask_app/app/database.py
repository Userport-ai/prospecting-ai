
import os
import re
import contextlib
from typing import Optional
from collections.abc import Generator
from pymongo.mongo_client import MongoClient
from pymongo.client_session import ClientSession
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from bson.objectid import ObjectId
from dotenv import load_dotenv
from models import (
    PersonProfile,
    PersonCurrentEmployment,
    PageContentInfo,
    LinkedInPost
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

    def _get_linkedin_posts_collection(self) -> Collection:
        """Returns LinkedIn posts collection."""
        return self.db['linkedin_posts']

    def _get_content_info_collection(self) -> Collection:
        """Returns Page details collection."""
        return self.db['content_info']

    def insert_person_profile(self, person_profile: PersonProfile) -> ObjectId:
        """Inserts Person information as a document in the database and returns the created Id."""
        if person_profile.id:
            raise ValueError(
                f"PersonProfile instance cannot have an Id before db insertion: {person_profile}")
        collection = self._get_person_profiles_collection()
        result = collection.insert_one(
            person_profile.model_dump(exclude=Database._exclude_id()))
        return result.inserted_id

    def insert_linkedin_post(self, linkedin_post: LinkedInPost, session: Optional[ClientSession] = None) -> ObjectId:
        """Inserts LinkedIn post information as document in the database and returns the created Id."""
        if linkedin_post.id:
            raise ValueError(
                f"LinkedInPost instance cannot have an Id before db insertion: {linkedin_post}")
        collection = self._get_linkedin_posts_collection()
        result = collection.insert_one(
            linkedin_post.model_dump(exclude=Database._exclude_id()), session=session)
        return result.inserted_id

    def insert_page_details(self, page_details: PageContentInfo, session: Optional[ClientSession] = None) -> ObjectId:
        """Inserts page details in the database and returns the created Id."""
        if page_details.id:
            raise ValueError(
                f"WebSearchresult instance cannot have an Id before db insertion: {page_details}")
        collection = self._get_content_info_collection()
        result = collection.insert_one(
            page_details.model_dump(exclude=Database._exclude_id()), session=session)
        return result.inserted_id

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

    def get_person_current_employment(self, person_profile_id: ObjectId) -> PersonCurrentEmployment:
        """Returns person and company details for given profile Id."""
        collection = self._get_person_profiles_collection()
        data_dict = collection.find_one({"_id": person_profile_id})
        if not data_dict:
            raise ValueError(
                f'Person profile not found for Id: {person_profile_id}')
        profile = PersonProfile(**data_dict)
        return Database.to_person_current_employement(profile=profile)

    def get_content_info_by_url(self, url: str) -> Optional[PageContentInfo]:
        """Returns page details for given url. Returns None if not found."""
        collection = self._get_content_info_collection()
        data_dict = collection.find_one({"url": url})
        if not data_dict:
            return None
        return PageContentInfo(**data_dict)

    @staticmethod
    def to_person_current_employement(profile: PersonProfile) -> PersonCurrentEmployment:
        """Returns PersonCurrentEmployment from given Person profile."""
        match = re.search("(.+) at (.+)", profile.occupation)
        if not match:
            raise ValueError(
                f"Profile occupation not in expected format: {profile}")
        role_title: str = match.group(1)
        company_name: str = match.group(2)

        # Find company URL from experiences.
        experience: Optional[PersonProfile.Experience] = next(
            filter(lambda e: e.company == company_name, profile.experiences), None)
        if not experience:
            raise ValueError(
                f"Could not find experience in profile with company: {company_name}. Profile: {profile}")
        company_linkedin_profile_url: str = experience.company_linkedin_profile_url

        return PersonCurrentEmployment(
            person_profile_id=profile.id,
            full_name=profile.full_name,
            role_title=role_title,
            company_name=company_name,
            company_linkedin_profile_url=company_linkedin_profile_url
        )

    def _test_connection(self):
        """Helper method to test successful connection to cluster deployment."""
        try:
            self.mongo_client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB wohoo!")
        except Exception as e:
            print(e)


if __name__ == "__main__":
    def read_person_profile():
        import json
        from utils import Utils
        data = None
        with open("../example_linkedin_info/proxycurl_profile_3.json", "r") as f:
            data = f.read()
        profile_data = json.loads(data)
        person_profile = PersonProfile(**profile_data)
        person_profile.linkedin_url = "https://in.linkedin.com/in/aniket-bajpai"
        # person_profile.linkedin_url = "https://www.linkedin.com/in/zperret"
        person_profile.date_synced = Utils.create_utc_time_now()
        return person_profile

    db = Database()
    db.insert_person_profile(person_profile=read_person_profile())
    # current_employment = db.get_current_employment(
    #     ObjectId("668e4eb26870b48c49e60dde"))
    # print(current_employment)
