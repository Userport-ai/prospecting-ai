import re
from langchain_community.callbacks import get_openai_callback
from typing import Optional
from langchain_core.pydantic_v1 import BaseModel, Field
import requests
import os
from markdownify import markdownify
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

OPENAI_EMBEDDING_FUNCTION = OpenAIEmbeddings(
    model="text-embedding-ada-002", api_key=os.environ["OPENAI_USERPORT_API_KEY"])

# url = "https://www.spkaa.com/blog/devops-world-2023-recap-and-the-best-highlights"
# url = "https://plaid.com/blog/year-in-review-2023/"
# This one below: 'More TechCrunch'. What a great job by GPT-40! Cost: 9K tokens by GPT40.
# url = "https://techcrunch.com/2023/09/19/plaids-zack-perret-on-visa-valuations-and-privacy/"
# url = "https://python.langchain.com/v0.2/docs/tutorials/classification/"
# url = "https://plaid.com/blog/introducing-plaid-layer/"
# This one returns None for the footer which is correct. Great job GPT-4O!
# url = "https://www.techstrongevents.com/devops-experience-2023/speakers"
# This one below: 'Helping you grow your business is our number one priority, if you would like to take your business to the next step just sign up!'
# which is incorrect but not by a lot, so technically still ok.
# url = "https://www.information-age.com/anuj-kapur-named-new-cloudbees-president-ceo-20109/"
# Super long post, cost 13K tokens by GPT40. It was correct, great job GPT-4O!!
# url = "https://daedtech.com/page/4/"
# This one didn't work first, it gave '### More From Forbes' first which was wrong but second one 'Join The Conversation' was right. So GPT-40 is not perfect.
# url = "https://www.forbes.com/sites/adrianbridgwater/2022/08/10/cloudbees-ceo-making-honey-in-the-software-delivery-hive/"
# url = "https://www.cloudbees.com/newsroom/cloudbees-appoints-raj-sarkar-as-chief-marketing-officer"
# url = "https://devops.com/cloudbees-ceo-state-of-software-development-is-a-disaster/"
# url = "https://www.cloudbees.com/blog/introducing-manual-workflow-triggers"
url = "https://www.cloudbees.com/events/details/eliminate-troubleshooting-headaches-with-pipeline-explorer-map"


html = requests.get(url).text
markdown_html = markdownify(html, heading_style="ATX")

with open("../example_linkedin_info/webpage.txt", "w") as f:
    f.write(html)

with open("../example_linkedin_info/webpage_markdown.txt", "w") as f:
    f.write(markdown_html)


# Markdown header splitter.
# headers_to_split_on = [("#", "Header 1"), ("##", "Header 2")]
headers_to_split_on = [("#", "Header 1")]
markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on, strip_headers=False)
md_header_splits = markdown_splitter.split_text(markdown_html)
print("num markdown splits: ", len(md_header_splits))
docs = [doc.page_content for doc in md_header_splits]

markdown_split_str = "\n\nSPLIT\n==================\n\n".join(docs)
with open("../example_linkedin_info/markdown_splits_combined.txt", "w") as f:
    f.write(markdown_split_str)

# My markdon splitter.


def find_h1_headings(text):
    # H1 pattern
    pattern = r'((?<!#)(#)\s.*)'
    # H2 pattern
    # pattern = r'((?<!#)(##)\s.*)'
    return re.findall(pattern, text, re.MULTILINE)


text = """
wn On AI And Taiwan At Computex 20
"""
h1_headings = find_h1_headings(markdown_html)
print(h1_headings)
if len(h1_headings) > 0:
    index = markdown_html.find(h1_headings[0][0])
    print("index: ", index)
    print("substring start: ", markdown_html[index:index+100])

# Semantic chunking splitter.
# input_splits = [md_split.page_content for md_split in md_header_splits[1:]]
# chunk_splitter = SemanticChunker(
#     OPENAI_EMBEDDING_FUNCTION,  breakpoint_threshold_type="gradient")
# sem_chunks = chunk_splitter.create_documents(input_splits)
# print("num sem chunks: ", len(sem_chunks))
# docs = [doc.page_content for doc in sem_chunks]

# semantic_split_str = "\n\nSPLIT\n==================\n\n".join(docs)
# with open("../example_linkedin_info/semantic_splits_combined.txt", "w") as f:
#     f.write(semantic_split_str)

# Recurive text splitter.
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=4096, chunk_overlap=200, add_start_index=True)
chunks = text_splitter.split_documents([Document(page_content=markdown_html)])
print("num recursive text chunks: ", len(chunks))
docs = [doc.page_content for doc in chunks]
text_split_str = "\n\nSPLIT\n==================\n\n".join(docs)
with open("../example_linkedin_info/recursive_text_splits_combined.txt", "w") as f:
    f.write(text_split_str)


# Custom splitter.
# We will look at the first page.


class FooterDetector(BaseModel):
    footer_first_sentence: Optional[str] = Field(
        default=None, description="First sentence from where the footer starts.")
    reason: str = Field(...,
                        description="Reason for why this was chosen as footer start point.")


OPENAI_GPT_3_5_TURBO_MODEL = os.environ["OPENAI_GPT_3_5_TURBO_MODEL"]
OPENAI_GPT_4O_MODEL = os.environ["OPENAI_GPT_4O_MODEL"]
OPENAI_API_KEY = os.environ["OPENAI_USERPORT_API_KEY"]
llm = ChatOpenAI(
    temperature=0, model_name=OPENAI_GPT_4O_MODEL, api_key=OPENAI_API_KEY).with_structured_output(FooterDetector)
last_chunk = md_header_splits[-1]
prompt_template = """
You are a smart web page analyzer. Given below is the final chunk of a parsed web page in Markdown format.
Can you identify if the chunk has footer containing a bunch of links that are unrelated to the remaining content?
If yes, return the first sentence where this footer starts. If no, return None.

Chunk:
{chunk}
"""
prompt = PromptTemplate.from_template(prompt_template)
chain = prompt | llm
print("\n")
# with get_openai_callback() as cb:
#     result = chain.invoke({"chunk": last_chunk})
#     print(result)
#     print("\ncost:")
#     print(cb)
# print("len last chunk: ", len(last_chunk.page_content))
