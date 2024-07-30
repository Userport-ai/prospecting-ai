import re
import urllib.parse


def detect_match(text, pattern):
    # Checking if a pattern matches the beginning
    match_result = re.match(pattern, text)
    if match_result:
        print(f"Match at the beginning: {match_result.group()}")
    else:
        print("No match at the beginning")
    return match_result


def find_all_md_links(text):
    # pattern = r"\[(.*?)\]\((.*?)\?trk=public_post.*?\)"
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    # pattern = r"\[([ ^\]]+)\]\(([^)]+)\?trk=public_post.*?\)"
    all_md_links = []
    for match in re.findall(pattern, text):
        # print("got match: ", match[1])
        link_suffix_pattern = r"(.*)\?trk=public_post.*"
        res = re.match(link_suffix_pattern, match[1])
        if res:
            all_md_links.append((match[0], res[1]))
        else:
            all_md_links.append((match[0], match[1]))

    for m in all_md_links:
        print(m)


author_state = "[![View profile for Anuj Kapur, graphic]()](https://www.linkedin.com/in/a2kapur?trk=public_post_feed-actor-image)"
author_state_pattern = r"\[!\[.*\]\(\)\]\(.*\)"

# author_name = "[Jean-Denis Greze](https://www.linkedin.com/in/jeandenisgreze?trk=public_post_feed-actor-name)"
# author_name = "[![View profile for Ha Phan, graphic]()](https://vn.linkedin.com/in/callmehaaa?trk=public_post_feed-actor-image)"
author_name = "[Anuj Kapur](https://www.linkedin.com/in/a2kapur?trk=public_post_reshare_feed-actor-name) "
name_pattern = r"\[(.*)\]\((.*)\?trk=public_post_.*feed.*\)"

post_url = "* [Report this post](/uas/login?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_ellipsis-menu-semaphore-sign-in-redirect&guestReportContentType=POST&_f=guest-reporting)"
post_url_pattern = r"\* \[Report this post\]\(.*session_redirect=(.*)\&trk=public_post.*\)"

# post_reactions = "[![]()![]()![]() 33](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_social-actions-reactions)"
post_reactions = "[![]()![]() 8](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Fjeandenisgreze_distributed-coroutines-a-new-primitive-soon-activity-7173787541630803969-ADdw&trk=public_post_social-actions-reactions)"
# post_reactions = "[![]()![]()![]() 1,012](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Fa2kapur_christian-klein-the-details-guy-who-has-activity-6728126001274068992-Accy&trk=public_post_social-actions-reactions)"
reaction_pattern = r"\[\!\[\].*\s* (\S*)\]\(.*\)"

post_comments = "[3 Comments](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_social-actions-comments)"
comments_pattern = r"\[(.*) Comments]\(.*\&trk=public_post_social-actions-comments\)"

like_button = "[Like](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_comment_like)"
like_pattern = r"\[Like]\(.*\&trk=public_post_comment_like\)"

card_links = "[![Distributed Coroutines: a new primitive soon in every developer’s toolkit]()## Distributed Coroutines: a new primitive soon in every developer’s toolkit### stealthrocket.tech](https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fstealthrocket%2Etech%2Fblog%2Fdistributed-coroutines%2F&urlhash=ALVW&trk=public_post_reshare_feed-article-content)"
card_links_pattern = r"\[\!\[(.*)\]\(\).*\]\(.*redirect\?url=(.*)\&urlhash.*\)"

# markdown_links = "Join us at [https://cloudbees.io](https://cloudbees.io?trk=public_post-text) for many more [https://lnkd.in/gmC2q4J7](https://lnkd.in/gmC2q4J7?trk=public_post_reshare-text)."
markdown_links = "[CloudBees](https://www.linkedin.com/company/cloudbees?trk=public_post_reshare-text) closed FY24 with a bang! Meeting and exceeding all targets. I want to thank our customers for the [#trust](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Ffeed%2Fhashtag%2Ftrust&trk=public_post_reshare-text) and all 🐝 for the hard work. And we celebrate being a [G2](https://www.linkedin.com/company/g2dotcom?trk=public_post_reshare-text) Top 3 Development Product ranking. Excited to be alongside [Microsoft](https://www.linkedin.com/company/microsoft?trk=public_post_reshare-text) [GitLab](https://www.linkedin.com/company/gitlab-com?trk=public_post_reshare-text). And we're hiring! [#DevSecOps](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Ffeed%2Fhashtag%2Fdevsecops&trk=public_post_reshare-text)"


publish_date_line = "mo"
publish_date_pattern = r'(\d+)mo'

# match = detect_match(post_reactions, reaction_pattern)
# print(int(match[1].replace(",", "")))
# print(match[1], urllib.parse.unquote(match[2]))
# find_all_md_links(markdown_links)

result = detect_match(author_name, name_pattern)
print("result: ", result[2])
