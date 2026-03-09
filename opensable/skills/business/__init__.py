"""
Business automation skills — CRM, pipeline, templates, follow-ups.
"""

from .crm_skill import CRMSkill
from .pipeline_skill import PipelineSkill
from .email_templates_skill import EmailTemplatesSkill
from .followup_skill import FollowUpSkill

__all__ = ["CRMSkill", "PipelineSkill", "EmailTemplatesSkill", "FollowUpSkill"]
