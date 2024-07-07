export const templateMessage = `Being a tech leader and handling a team of 30+ engineers, does your team face challenges with searching of info scattered across different internals apps, outside coding?\n
Asking this as speaking with some of our engineering customers like X and Y , I've learned that a major challenge facing engineering teams today is productivity being hindered by time spent searching for technical documentation within the SDLC, but no worries- Glean solves this problem and much more!\n
To save your team from spending 20% of every workday looking for information, do you mind spending 20 mins to see Glean in action?`;

export const exampleTemplate = {
  roleTitles: "SVP of Marketing",
  additionalKeywords: "Performance Marketing",
  message: templateMessage,
};

var createdMessages = [exampleTemplate, exampleTemplate];
export function getTemplateMessages() {
  return createdMessages;
}
