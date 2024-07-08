from googlesearch import search
from typing import List


class Websearch:

    @staticmethod
    def run(query: str, max_results: int = 20) -> List[str]:
        """Returns google search result URLs (upto specified maximum) for given input query.

        Args:
            query [str]: user query

        Returns:
            [list]: List of URLs fetched from Google search.
        """
        res_urls: List[str] = []
        for url in search(query, stop=max_results):
            res_urls.append(url)
        return res_urls


if __name__ == "__main__":
    # query = "aniket bajpai limechat ceo recent linkedin posts"
    query = "Zachary Perret Plaid CEO recent LinkedIn posts"
    # query = "Anuj Kapur CEO Cloudbees recent articles or blogs"
    for url in Websearch.run(query=query, max_results=20):
        print(url)
