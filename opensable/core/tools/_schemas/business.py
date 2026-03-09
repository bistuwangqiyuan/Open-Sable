"""
Tool schemas for Business automation domain — CRM, Pipeline, Templates, Follow-ups.
"""

SCHEMAS = [
    # ══════════════════════════════════════════════════════════════════════
    # CRM CONTACTS
    # ══════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "crm_add_contact",
            "description": "Add a new contact to the CRM. Use for manufacturers, buyers, suppliers, or any business contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name of the contact person"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "company": {"type": "string", "description": "Company/organization name"},
                    "country": {"type": "string", "description": "Country (e.g. 'Turkey', 'Germany')"},
                    "city": {"type": "string", "description": "City"},
                    "role": {"type": "string", "enum": ["manufacturer", "buyer", "supplier", "partner", "prospect"], "description": "Business role"},
                    "industry": {"type": "string", "description": "Industry sector (e.g. 'textile', 'fashion')"},
                    "products": {"type": "string", "description": "Comma-separated products (e.g. 'denim,cotton,linen')"},
                    "source": {"type": "string", "enum": ["web_search", "referral", "inbound", "linkedin", "manual"], "description": "How the contact was found"},
                    "tags": {"type": "string", "description": "Comma-separated tags"},
                    "notes": {"type": "string", "description": "Free-form notes"},
                    "website": {"type": "string", "description": "Company website URL"},
                    "score": {"type": "integer", "description": "Lead score 0-100"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_search_contacts",
            "description": "Search CRM contacts by name/email/company, role, status, country, or tags. Returns matching contacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text (matches name, email, company)"},
                    "role": {"type": "string", "enum": ["manufacturer", "buyer", "supplier", "partner", "prospect"], "description": "Filter by role"},
                    "status": {"type": "string", "enum": ["new", "contacted", "replied", "qualified", "inactive", "blacklisted"], "description": "Filter by status"},
                    "country": {"type": "string", "description": "Filter by country"},
                    "tags": {"type": "string", "description": "Filter by tag"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_get_contact",
            "description": "Get full details of a specific CRM contact by their ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                },
                "required": ["contact_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_update_contact",
            "description": "Update fields on an existing CRM contact (status, notes, score, next_followup, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID to update"},
                    "status": {"type": "string", "enum": ["new", "contacted", "replied", "qualified", "inactive", "blacklisted"], "description": "New status"},
                    "notes": {"type": "string", "description": "Updated notes"},
                    "score": {"type": "integer", "description": "Updated lead score 0-100"},
                    "next_followup": {"type": "string", "description": "Next follow-up date (ISO format)"},
                    "products": {"type": "string", "description": "Updated product list"},
                    "tags": {"type": "string", "description": "Updated tags"},
                    "role": {"type": "string", "description": "Updated role"},
                },
                "required": ["contact_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_delete_contact",
            "description": "Delete a contact and all their activity history from the CRM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID to delete"},
                },
                "required": ["contact_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_log_activity",
            "description": "Log an interaction with a CRM contact (email sent, reply received, call, meeting, note).",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "activity_type": {"type": "string", "enum": ["email_sent", "email_received", "note", "call", "meeting", "status_change"], "description": "Type of activity"},
                    "subject": {"type": "string", "description": "Activity subject/summary"},
                    "body": {"type": "string", "description": "Full text/details"},
                    "metadata": {"type": "string", "description": "Extra data as JSON string"},
                },
                "required": ["contact_id", "activity_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_get_activities",
            "description": "Get interaction history for a CRM contact (emails, calls, notes, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": ["contact_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crm_stats",
            "description": "Get CRM statistics: total contacts, counts by role/status/country.",
            "parameters": {"type": "object", "properties": {}},
        },
    },

    # ══════════════════════════════════════════════════════════════════════
    # PIPELINE / DEALS
    # ══════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "pipeline_create_deal",
            "description": "Create a new deal in the sales pipeline. Links a buyer and manufacturer with product/quantity/delivery details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Deal title (e.g. 'Denim Supply for FashionCo Germany')"},
                    "buyer_id": {"type": "string", "description": "CRM contact ID of the buyer"},
                    "manufacturer_id": {"type": "string", "description": "CRM contact ID of the manufacturer"},
                    "product": {"type": "string", "description": "Product type (e.g. 'denim fabric', 'cotton yarn')"},
                    "quantity": {"type": "string", "description": "Quantity needed (e.g. '10000')"},
                    "unit": {"type": "string", "description": "Unit of measure (meters, kg, pieces, etc.)"},
                    "quality_requirements": {"type": "string", "description": "Quality specs (e.g. 'EU Oeko-Tex certified, 12oz weight')"},
                    "delivery_date": {"type": "string", "description": "Target delivery date"},
                    "price_range": {"type": "string", "description": "Expected price range (e.g. '3.50-4.50 per meter')"},
                    "currency": {"type": "string", "description": "Currency (default EUR)"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "description": "Deal priority"},
                    "notes": {"type": "string", "description": "Additional notes"},
                    "value_estimate": {"type": "number", "description": "Estimated deal value in EUR"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_advance_deal",
            "description": "Move a deal to the next pipeline stage. Stages: prospect → qualified → proposal → negotiation → won | lost",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string", "description": "Deal ID"},
                    "new_stage": {"type": "string", "enum": ["prospect", "qualified", "proposal", "negotiation", "won", "lost"], "description": "New stage"},
                    "reason": {"type": "string", "description": "Reason for the stage change"},
                },
                "required": ["deal_id", "new_stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_get_deal",
            "description": "Get full details of a specific deal including product, quantity, quality requirements, and linked contacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string", "description": "Deal ID"},
                },
                "required": ["deal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_list_deals",
            "description": "List deals in the pipeline, optionally filtered by stage, buyer, or manufacturer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "enum": ["prospect", "qualified", "proposal", "negotiation", "won", "lost"], "description": "Filter by stage"},
                    "buyer_id": {"type": "string", "description": "Filter by buyer contact ID"},
                    "manufacturer_id": {"type": "string", "description": "Filter by manufacturer contact ID"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_update_deal",
            "description": "Update deal details (product, quantity, price, notes, etc.). Use pipeline_advance_deal for stage changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string", "description": "Deal ID to update"},
                    "product": {"type": "string", "description": "Updated product"},
                    "quantity": {"type": "string", "description": "Updated quantity"},
                    "quality_requirements": {"type": "string", "description": "Updated quality specs"},
                    "delivery_date": {"type": "string", "description": "Updated delivery date"},
                    "price_range": {"type": "string", "description": "Updated price range"},
                    "notes": {"type": "string", "description": "Updated notes"},
                    "value_estimate": {"type": "number", "description": "Updated value estimate"},
                    "buyer_id": {"type": "string", "description": "Link/change buyer"},
                    "manufacturer_id": {"type": "string", "description": "Link/change manufacturer"},
                },
                "required": ["deal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_stats",
            "description": "Get pipeline statistics: deals per stage, total values, conversion metrics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_match",
            "description": "View a deal with its linked buyer and manufacturer contact details for matching/comparison.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string", "description": "Deal ID"},
                },
                "required": ["deal_id"],
            },
        },
    },

    # ══════════════════════════════════════════════════════════════════════
    # EMAIL TEMPLATES
    # ══════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "template_list",
            "description": "List available email templates. Includes outreach, follow-up, inquiry, and proposal templates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["outreach", "followup", "inquiry", "proposal", "notification"], "description": "Filter by category"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "template_get",
            "description": "Get a specific email template with its full body and list of merge fields (e.g. {{name}}, {{company}}).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Template name (e.g. 'manufacturer_introduction', 'followup_no_reply')"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "template_save",
            "description": "Create or update an email template. Use {{field_name}} for merge fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Template name (unique identifier)"},
                    "subject": {"type": "string", "description": "Email subject with optional merge fields"},
                    "body": {"type": "string", "description": "Email body with merge fields like {{name}}, {{company}}, etc."},
                    "category": {"type": "string", "enum": ["outreach", "followup", "inquiry", "proposal", "notification"], "description": "Template category"},
                    "language": {"type": "string", "description": "Language code (default 'en')"},
                    "tags": {"type": "string", "description": "Comma-separated tags"},
                },
                "required": ["name", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "template_render",
            "description": "Render an email template by filling in merge fields. Returns ready-to-send subject and body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Template name to render"},
                    "fields": {"type": "object", "description": "Merge field values, e.g. {\"name\": \"John\", \"company\": \"Acme\", \"my_company\": \"TextileBridge\"}"},
                },
                "required": ["name", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "template_delete",
            "description": "Delete an email template by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Template name to delete"},
                },
                "required": ["name"],
            },
        },
    },

    # ══════════════════════════════════════════════════════════════════════
    # FOLLOW-UPS
    # ══════════════════════════════════════════════════════════════════════
    {
        "type": "function",
        "function": {
            "name": "followup_recommendations",
            "description": "Get AI-generated follow-up recommendations: overdue contacts, stale leads, stalling deals. Includes suggested templates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_recommendations": {"type": "integer", "description": "Max recommendations (default 10)"},
                    "stale_days": {"type": "integer", "description": "Days without reply to consider stale (default 5)"},
                    "stalling_days": {"type": "integer", "description": "Days in same stage to consider stalling (default 7)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "followup_overdue",
            "description": "List contacts whose scheduled follow-up date has passed and need attention.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "followup_stale",
            "description": "List contacts who were contacted but haven't replied after N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days since last contact (default 5)"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "followup_summary",
            "description": "Get a comprehensive business summary: CRM stats, pipeline stats, overdue follow-ups, and suggested next actions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
