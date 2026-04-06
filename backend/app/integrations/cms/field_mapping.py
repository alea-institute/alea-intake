"""Canonical ALEA -> CMS field mapping functions.

Produces CMS-neutral canonical dicts from ALEA intake entities.
Each CMS adapter further maps these canonical fields to its
CMS-specific field names (Clio, MyCase, LegalServer).

This two-layer mapping isolates CMS-specific quirks from the
shared sync logic.
"""

from __future__ import annotations

from typing import Any


def map_intake_to_cms_contact(intake: dict, party: dict) -> dict[str, Any]:
    """Map ALEA intake party data to canonical CMS contact fields.

    Args:
        intake: The intake record dict (provides context).
        party: The party dict with name, email, phone, etc.

    Returns:
        Canonical contact dict with {name, email, phone, type}.
    """
    first = party.get("first_name", "")
    last = party.get("last_name", "")
    name = f"{first} {last}".strip() if (first or last) else party.get("name", "Unknown")

    return {
        "name": name,
        "email": party.get("email", ""),
        "phone": party.get("phone", ""),
        "type": party.get("party_type", "person"),
        "alea_intake_id": intake.get("id"),
    }


def map_intake_to_cms_matter(intake: dict, analysis_run: dict) -> dict[str, Any]:
    """Map ALEA intake + analysis to canonical CMS matter fields.

    Args:
        intake: The intake record dict.
        analysis_run: The analysis run dict with status, practice area, etc.

    Returns:
        Canonical matter dict with {description, status, practice_area, client_id}.
    """
    return {
        "description": intake.get("description", "ALEA Intake"),
        "status": analysis_run.get("status", "open"),
        "practice_area": analysis_run.get("practice_area", ""),
        "client_id": analysis_run.get("client_id", ""),
        "alea_intake_id": intake.get("id"),
        "alea_run_id": analysis_run.get("id"),
    }


def map_output_to_cms_document(output_doc: dict, format: str) -> dict[str, Any]:
    """Map ALEA output document to canonical CMS document fields.

    Args:
        output_doc: The output document dict.
        format: Target format (pdf, docx, markdown).

    Returns:
        Canonical document dict with {name, content_type, description}.
    """
    profile = output_doc.get("profile_type", "document")
    doc_id = output_doc.get("id", "unknown")

    content_type_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "markdown": "text/markdown",
    }

    return {
        "name": f"ALEA_{profile}_{doc_id}.{format}",
        "content_type": content_type_map.get(format, "application/octet-stream"),
        "description": f"ALEA Intake {profile.replace('_', ' ').title()} output",
        "alea_output_id": doc_id,
        "format": format,
    }
