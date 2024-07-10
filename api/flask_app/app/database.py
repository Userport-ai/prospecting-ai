
import os
import re
from typing import Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from bson.objectid import ObjectId
from dotenv import load_dotenv
from models import (
    PersonProfile,
    CurrentEmployment,
    WebSearchResult
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

    def _get_web_search_results_collection(self) -> Collection:
        """Returns Web Search results collection."""
        return self.db['web_search_results']

    def insert_person_profile(self, person_profile: PersonProfile) -> ObjectId:
        """Inserts Person information as a document in the database and returns the created Id."""
        if person_profile.id:
            raise ValueError(
                f"PersonProfile instance cannot have an Id before db insertion: {person_profile}")
        collection = self._get_person_profiles_collection()
        result = collection.insert_one(
            person_profile.model_dump(exclude=Database._exclude_id()))
        return result.inserted_id

    def insert_web_search_result(self, web_search_result: WebSearchResult) -> ObjectId:
        """Inserts Websearch result as a document in the database and returns the created Id."""
        if web_search_result.id:
            raise ValueError(
                f"WebSearchresult instance cannot have an Id before db insertion: {web_search_result}")
        collection = self._get_web_search_results_collection()
        result = collection.insert_one(
            web_search_result.model_dump(exclude=Database._exclude_id()))
        return result.inserted_id

    def get_current_employment(self, person_profile_id: ObjectId) -> CurrentEmployment:
        """Returns CurrentEmployment value for given person's profile id."""
        collection = self._get_person_profiles_collection()
        data_dict = collection.find_one({"_id": person_profile_id})
        if not data_dict:
            raise ValueError(
                f'Person profile not found for Id: {person_profile_id}')
        profile = PersonProfile(**data_dict)
        return Database._to_current_employment(profile=profile)

    def get_web_search_result_by_url(self, url: str) -> Optional[WebSearchResult]:
        """Returns Websearch result for given url and None if not found."""
        collection = self._get_web_search_results_collection()
        data_dict = collection.find_one({"url": url})
        if not data_dict:
            return None
        return WebSearchResult(**data_dict)

    @staticmethod
    def _to_current_employment(profile: PersonProfile) -> CurrentEmployment:
        """Returns CurrentEmployment from given Person profile."""
        match = re.search("(.+) at (.+)", profile.occupation)
        if not match:
            raise ValueError(
                f"Profile occupation not in expected format: {profile}")
        role_title: str = match.group(1)
        company_name: str = match.group(2)

        # Find company URL from experiences.
        experience: PersonProfile.Experience = next(
            filter(lambda e: e.company == company_name, profile.experiences), None)
        if not experience:
            raise ValueError(
                f"Could not find experience in profile with company: {company_name}. Profile: {profile}")
        company_linkedin_profile_url: str = experience.company_linkedin_profile_url

        return CurrentEmployment(
            person_profile_id=profile.id,
            date_synced=profile.date_synced,
            full_name=profile.full_name,
            role_title=role_title,
            person_profile_url=profile.linkedin_url,
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
