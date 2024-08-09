// const engTemplateMessage = `Being a tech leader and handling a team of 30+ engineers, does your team face challenges with searching of info scattered across different internals apps, outside coding?\n
// Asking this as speaking with some of our engineering customers like X and Y , I've learned that a major challenge facing engineering teams today is productivity being hindered by time spent searching for technical documentation within the SDLC, but no worries- Glean solves this problem and much more!\n
// To save your team from spending 20% of every workday looking for information, do you mind spending 20 mins to see Glean in action?`;

const hrTemplateMessage = `Do you have visibility when employees are not feeling the most productive in your organization today?\n
We have spoken to a ton of HR leaders from Visa and Stripe and they all attest to an experience where it's very hard to track employee morale at scale.\n
To ensure employees don't leave for your competition due to morale issues, do you mind spending 20 minutes to learn about WorkHR?`;

// Exporting to use in Lead result page.
export const ceoTemplateMessage = `Given you lead an team of more than 1000 employees, do you face challenges understanding the sentiment of your team after major announcements?\n
Asking this as speaking with some of our customers like Visa and Stripe, I've learned that a major challenge facing unicorn companies is the impact of big announcements on employee productivity.\n
To keep track of your employees sentiments, do you mind spending 20 minutes to see WorkHR in action?`;

export const exampleTemplate = {
  roleTitles: "VP of HR",
  message: hrTemplateMessage,
};

export const vpMarketingTemplate = {
  roleTitles: "VP of Marketing",
  description: "Experience in Performance Marketing",
  message: ceoTemplateMessage,
};

var createdMessages = [exampleTemplate];

export function getTemplateMessages() {
  return createdMessages;
}

export function createTemplateMessage() {
  createdMessages.push(vpMarketingTemplate);
  return createdMessages;
}
