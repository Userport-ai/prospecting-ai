import { http, HttpResponse } from "msw";
import {
  leadsResult,
  emptyLeadsResult,
  leadsInProgressResult,
} from "./leads-table-data";
import {
  exampleTemplateResponse,
  editTemplateResponse,
  noTemplatesResponse,
} from "./create-template-data";
import { reportWithSelectedTemplate } from "./lead-report-with-template-data";
import { reportWithNoTemplate } from "./lead-report-no-template-data";

export const handlers = [
  http.get("/api/v1/leads", () => {
    return HttpResponse.json(leadsResult);
  }),
  http.get("/api/v1/outreach-email-templates", () => {
    return HttpResponse.json(exampleTemplateResponse);
  }),
  http.get("/api/v1/outreach-email-templates/*", () => {
    return HttpResponse.json(editTemplateResponse);
  }),
  http.get("/api/v1/lead-research-reports/*", () => {
    return HttpResponse.json(reportWithNoTemplate);
  }),
];
