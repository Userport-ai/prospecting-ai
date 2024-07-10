
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from bson.objectid import ObjectId
from dotenv import load_dotenv
from database_models import PersonProfile, CompanyInfo, WebSearchResult
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

    def _get_person_profile_collection(self) -> Collection:
        """Returns Person Profile collection."""
        return self.db['person_profile']

    def _get_company_info_collection(self) -> Collection:
        """Returns Company Info collection."""
        return self.db['company_info']

    def _get_web_search_results_collection(self) -> Collection:
        """Returns Web Search results collection."""
        return self.db['web_search_results']

    def insert_person_profile(self, person_profile: PersonProfile) -> ObjectId:
        """Inserts Person information as a document in the database and returns the created Id."""
        if person_profile.id:
            raise ValueError(
                f"PersonProfile instance cannot have an Id before db insertion: {person_profile}")
        person_profile_collection = self._get_person_profile_collection()
        result = person_profile_collection.insert_one(
            person_profile.model_dump(exclude=Database._exclude_id()))
        return result.inserted_id

    def insert_company_info(self, company_info: CompanyInfo) -> ObjectId:
        """Inserts Company information as a document in the database and returns the created Id."""
        if company_info.id:
            raise ValueError(
                f"CompanyInfo instance cannot have an Id before db insertion: {company_info}")
        company_info_collection = self._get_company_info_collection()
        result = company_info_collection.insert_one(
            company_info.model_dump(exclude=Database._exclude_id()))
        return result.inserted_id

    def insert_web_search_result(self, web_search_result: WebSearchResult) -> ObjectId:
        """Inserts Websearch result as a document in the database and returns the created Id."""
        if web_search_result.id:
            raise ValueError(
                f"WebSearchresult instance cannot have an Id before db insertion: {web_search_result}")
        web_search_results_collection = self._get_web_search_results_collection()
        result = web_search_results_collection.insert_one(
            web_search_result.model_dump(exclude=Database._exclude_id()))
        return result.inserted_id

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
        person_profile.date_synced = Utils.create_utc_time_now()
        return person_profile

    db = Database()
    db.insert_person_profile(person_profile=read_person_profile())

    # company_info = CompanyInfo(
    #     full_name="Plaid", linkedin_page_url="https://www.linkedin.com/company/plaid-/")
    # db.insert_company_info(company_info=company_info)
