
import os
import contextlib
from typing import Optional
from collections.abc import Generator
from pymongo.mongo_client import MongoClient
from pymongo.client_session import ClientSession
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from bson.objectid import ObjectId
from dotenv import load_dotenv
from utils import Utils
from models import (
    PersonProfile,
    ContentDetails,
    LinkedInPost,
    WebPage
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

    def _get_web_pages_collection(self) -> Collection:
        """Returns Web Page collection."""
        return self.db['web_pages']

    def _get_content_details_collection(self) -> Collection:
        """Returns content details collection."""
        return self.db['content_details']

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

        collection = self._get_content_details_collection()
        result = collection.insert_one(
            content_details.model_dump(exclude=Database._exclude_id()), session=session)
        return str(result.inserted_id)

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

    def get_content_details_by_url(self, url: str) -> Optional[ContentDetails]:
        """Returns Content details for given url. Returns None if not found."""
        collection = self._get_content_details_collection()
        data_dict = collection.find_one({"url": url})
        if not data_dict:
            return None
        return ContentDetails(**data_dict)

    def get_content_details(self, content_details_id: str) -> Optional[ContentDetails]:
        """Returns Content details for given ID."""
        collection = self._get_content_details_collection()
        data_dict = collection.find_one({"_id": ObjectId(content_details_id)})
        if not data_dict:
            raise ValueError(
                f'Content Details not found for Id: {content_details_id}')
        return ContentDetails(**data_dict)

    def _test_connection(self):
        """Helper method to test successful connection to cluster deployment."""
        try:
            self.mongo_client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB wohoo!")
        except Exception as e:
            print(e)


if __name__ == "__main__":

    db = Database()
    content_details_id = '66a72585e3aa5e1d1f9afc79'
    details = db.get_content_details(content_details_id=content_details_id)
    print("details person profile: ", details.person_profile_id,
          type(details.person_profile_id))
    print("details web page ref: ", details.web_page_ref_id,
          type(details.web_page_ref_id))
    print("details linkedin post ref : ", details.linkedin_post_ref_id,
          type(details.linkedin_post_ref_id))
    print("details id : ", details.id,
          type(details.id))
