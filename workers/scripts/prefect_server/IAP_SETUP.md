# IAP Setup for Prefect Server

This document outlines the Identity-Aware Proxy (IAP) configuration for the Prefect Server running on Cloud Run.

## Service Account

A dedicated service account has been created for IAP:
- Name: `iap-prefect-sa`
- Email: `iap-prefect-sa@omega-winter-431704-u5.iam.gserviceaccount.com`
- Purpose: Handles authentication and authorization for IAP

## IAP Configuration

The IAP is configured to:
1. Restrict access to the Prefect Server to only authenticated users
2. Allow only users from the `userport.ai` domain and specifically `sowrabh@userport.ai`
3. Provide secure authenticated access to the Prefect Server UI and API

## OAuth Configuration

An OAuth client has been created for IAP with:
- Application type: Internal
- Application name: Prefect Server IAP
- Support email: sowrabh@userport.ai

## Access URLs

The Prefect Server is accessible at:
- URL: https://prefect-server-116199002084.us-east1.run.app

## Authentication Flow

1. Users navigate to the Prefect Server URL
2. IAP intercepts the request and verifies the user's identity
3. If authenticated and authorized, the user gains access to the Prefect Server
4. The service account handles backend authentication between IAP and Cloud Run

## Permissions

The following IAM roles have been assigned:
- `roles/iap.httpsResourceAccessor`: Granted to the domain `userport.ai`, user `sowrabh@userport.ai`, and the IAP service account
- `roles/run.invoker`: Granted to the domain `userport.ai`, user `sowrabh@userport.ai`, and the IAP service account
- `roles/run.admin`: Granted to user `sowrabh@userport.ai`