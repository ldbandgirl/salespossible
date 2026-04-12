"""
CRM tool — HubSpot, Salesforce, or mock backend.

Provider is set in config.yaml: crm.provider = hubspot | salesforce | mock

The mock backend stores data in-process for dev/testing without credentials.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── Anthropic tool schemas ─────────────────────────────────────────────────────

CRM_LOOKUP_SCHEMA: dict[str, Any] = {
    "name": "crm_lookup",
    "description": (
        "Look up contacts, companies, or deals in the CRM. "
        "Returns matching records with contact info, company details, deal stage, and notes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Name, email, company name, or keyword to search",
            },
            "record_type": {
                "type": "string",
                "enum": ["contact", "company", "deal", "any"],
                "description": "Type of CRM record to look up",
                "default": "any",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}

CRM_CREATE_CONTACT_SCHEMA: dict[str, Any] = {
    "name": "crm_create_contact",
    "description": "Create a new contact in the CRM.",
    "input_schema": {
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "email": {"type": "string"},
            "company": {"type": "string"},
            "title": {"type": "string"},
            "phone": {"type": "string"},
            "notes": {"type": "string", "description": "Initial notes about this contact"},
        },
        "required": ["first_name", "last_name", "email"],
    },
}

CRM_UPDATE_DEAL_SCHEMA: dict[str, Any] = {
    "name": "crm_update_deal",
    "description": (
        "Update an existing deal in the CRM — stage, amount, close date, or notes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "deal_id": {"type": "string", "description": "Deal ID or name"},
            "stage": {
                "type": "string",
                "enum": [
                    "prospecting",
                    "qualification",
                    "proposal",
                    "negotiation",
                    "closed_won",
                    "closed_lost",
                ],
            },
            "amount": {"type": "number", "description": "Deal value in USD"},
            "close_date": {
                "type": "string",
                "description": "Expected close date (YYYY-MM-DD)",
            },
            "notes": {"type": "string"},
        },
        "required": ["deal_id"],
    },
}


# ── Tool functions ────────────────────────────────────────────────────────────

async def crm_lookup(inputs: dict[str, Any]) -> str:
    provider = _get_provider()
    return await provider.lookup(
        query=inputs["query"],
        record_type=inputs.get("record_type", "any"),
        limit=int(inputs.get("limit", 5)),
    )


async def crm_create_contact(inputs: dict[str, Any]) -> str:
    provider = _get_provider()
    return await provider.create_contact(inputs)


async def crm_update_deal(inputs: dict[str, Any]) -> str:
    provider = _get_provider()
    return await provider.update_deal(inputs)


def _get_provider() -> "BaseCRMProvider":
    crm_provider = os.environ.get("CRM_PROVIDER", "mock").lower()
    if crm_provider == "hubspot":
        return HubSpotProvider(os.environ.get("HUBSPOT_API_KEY", ""))
    elif crm_provider == "salesforce":
        return SalesforceProvider()
    else:
        return MockCRMProvider()


# ── Providers ─────────────────────────────────────────────────────────────────

class BaseCRMProvider:
    async def lookup(self, query: str, record_type: str, limit: int) -> str:
        raise NotImplementedError

    async def create_contact(self, data: dict[str, Any]) -> str:
        raise NotImplementedError

    async def update_deal(self, data: dict[str, Any]) -> str:
        raise NotImplementedError


class MockCRMProvider(BaseCRMProvider):
    """In-memory CRM for development and testing."""

    _contacts: list[dict[str, Any]] = [
        {
            "id": "c001",
            "type": "contact",
            "first_name": "Sarah",
            "last_name": "Chen",
            "email": "s.chen@acmecorp.com",
            "company": "Acme Corp",
            "title": "VP of Sales",
            "phone": "+1-555-0101",
            "notes": "Interested in enterprise plan. Follow up after Q2.",
            "deal_stage": "proposal",
        },
        {
            "id": "c002",
            "type": "contact",
            "first_name": "Marcus",
            "last_name": "Rivera",
            "email": "m.rivera@globex.io",
            "company": "Globex",
            "title": "CTO",
            "phone": "+1-555-0202",
            "notes": "Technical buyer. Needs security questionnaire filled.",
            "deal_stage": "negotiation",
        },
        {
            "id": "d001",
            "type": "deal",
            "name": "Acme Corp — Enterprise",
            "contact": "s.chen@acmecorp.com",
            "company": "Acme Corp",
            "stage": "proposal",
            "amount": 48000,
            "close_date": "2026-06-30",
        },
    ]

    async def lookup(self, query: str, record_type: str, limit: int) -> str:
        lower = query.lower()
        results = [
            r for r in self._contacts
            if (
                lower in json.dumps(r).lower()
                and (record_type == "any" or r.get("type") == record_type)
            )
        ][:limit]

        if not results:
            return f"No CRM records found matching '{query}'"

        lines = [f"CRM results for '{query}':\n"]
        for r in results:
            lines.append(json.dumps(r, indent=2))
        return "\n".join(lines)

    async def create_contact(self, data: dict[str, Any]) -> str:
        import uuid
        new = {"id": str(uuid.uuid4())[:8], "type": "contact", **data}
        self._contacts.append(new)
        return f"Contact created: {data.get('first_name')} {data.get('last_name')} (ID: {new['id']})"

    async def update_deal(self, data: dict[str, Any]) -> str:
        deal_id = data.pop("deal_id")
        for r in self._contacts:
            if r.get("type") == "deal" and (
                r.get("id") == deal_id or deal_id.lower() in r.get("name", "").lower()
            ):
                r.update(data)
                return f"Deal updated: {r.get('name', deal_id)} → {json.dumps(data)}"
        return f"Deal not found: {deal_id}"


class HubSpotProvider(BaseCRMProvider):
    """HubSpot CRM integration via v3 API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.hubapi.com"

    async def lookup(self, query: str, record_type: str, limit: int) -> str:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}"}

        endpoints = {
            "contact": f"/crm/v3/objects/contacts/search",
            "company": f"/crm/v3/objects/companies/search",
            "deal": f"/crm/v3/objects/deals/search",
        }

        record_types = (
            [record_type] if record_type != "any" else ["contact", "company", "deal"]
        )

        all_results = []
        async with httpx.AsyncClient() as client:
            for rt in record_types:
                endpoint = endpoints.get(rt)
                if not endpoint:
                    continue
                resp = await client.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json={
                        "query": query,
                        "limit": limit,
                        "properties": ["firstname", "lastname", "email", "company",
                                       "dealname", "dealstage", "amount"],
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    all_results.extend(data.get("results", []))

        if not all_results:
            return f"No HubSpot records found for '{query}'"

        return json.dumps(all_results[:limit], indent=2)[:3000]

    async def create_contact(self, data: dict[str, Any]) -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "properties": {
                "firstname": data.get("first_name", ""),
                "lastname": data.get("last_name", ""),
                "email": data.get("email", ""),
                "company": data.get("company", ""),
                "jobtitle": data.get("title", ""),
                "phone": data.get("phone", ""),
                "hs_lead_status": "NEW",
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=headers,
                json=payload,
            )
        if resp.status_code in (200, 201):
            result = resp.json()
            return f"HubSpot contact created (ID: {result.get('id')})"
        return f"HubSpot error: {resp.status_code} {resp.text[:200]}"

    async def update_deal(self, data: dict[str, Any]) -> str:
        import httpx

        deal_id = data.pop("deal_id")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"properties": {}}
        if "stage" in data:
            payload["properties"]["dealstage"] = data["stage"]
        if "amount" in data:
            payload["properties"]["amount"] = str(data["amount"])
        if "close_date" in data:
            payload["properties"]["closedate"] = data["close_date"]
        if "notes" in data:
            payload["properties"]["description"] = data["notes"]

        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self.base_url}/crm/v3/objects/deals/{deal_id}",
                headers=headers,
                json=payload,
            )
        if resp.status_code == 200:
            return f"HubSpot deal {deal_id} updated"
        return f"HubSpot error: {resp.status_code} {resp.text[:200]}"


class SalesforceProvider(BaseCRMProvider):
    """Salesforce integration stub — extend with simple-salesforce library."""

    async def lookup(self, query: str, record_type: str, limit: int) -> str:
        return (
            "Salesforce provider not yet configured. "
            "Set CRM_PROVIDER=hubspot or CRM_PROVIDER=mock, "
            "or implement SalesforceProvider using the simple-salesforce library."
        )

    async def create_contact(self, data: dict[str, Any]) -> str:
        return "Salesforce provider not configured."

    async def update_deal(self, data: dict[str, Any]) -> str:
        return "Salesforce provider not configured."
