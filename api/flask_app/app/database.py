
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from bson.objectid import ObjectId
from dotenv import load_dotenv
from database_models import PersonInfo, CompanyInfo, WebSearchResult
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

    def _get_person_info_collection(self) -> Collection:
        """Returns Person Info collection."""
        return self.db['person_info']

    def _get_company_info_collection(self) -> Collection:
        """Returns Company Info collection."""
        return self.db['company_info']

    def _get_web_search_results_collection(self) -> Collection:
        """Returns Web Search results collection."""
        return self.db['web_search_results']

    def insert_person_info(self, person_info: PersonInfo) -> ObjectId:
        """Inserts Person information as a document in the database and returns the created Id."""
        if person_info.id:
            raise ValueError(
                f"PersonInfo instance cannot have an Id before db insertion: {person_info}")
        person_info_collection = self._get_person_info_collection()
        result = person_info_collection.insert_one(
            person_info.model_dump(exclude=Database._exclude_id()))
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
    db = Database()
    person_info = PersonInfo(full_name="Zachary Perret",
                             linkedin_profile_url="https://www.linkedin.com/in/zperret/")

    company_info = CompanyInfo(
        full_name="Plaid", linkedin_page_url="https://www.linkedin.com/company/plaid-/")
    db.insert_person_info(person_info=person_info)
    db.insert_company_info(company_info=company_info)
