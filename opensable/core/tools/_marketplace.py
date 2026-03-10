"""
Marketplace Tool Mixin,  Skills Store integration for the agent.

Tools:
  marketplace_search   ,  Search the SableCore Skills Marketplace
  marketplace_info     ,  Get detailed info about a specific skill
  marketplace_install  ,  Install a skill (requires user approval via HITL)
  marketplace_review   ,  Post a review on a skill the agent has used

All operations go through the Agent Gateway Protocol (SAGP/1.0)
with Ed25519 + HMAC-SHA512 + NaCl encryption.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class MarketplaceToolsMixin:
    """Marketplace tools injected into the ToolRegistry."""

    # ── lazy import to avoid circular deps ──

    def _get_skill_registry(self):
        """Get or create the SkillRegistry singleton (lazy)."""
        if not hasattr(self, "_skill_registry") or self._skill_registry is None:
            try:
                from ..skills_marketplace import SkillRegistry
                self._skill_registry = SkillRegistry(self.config)
            except Exception as e:
                logger.warning(f"SkillRegistry init failed: {e}")
                self._skill_registry = None
        return self._skill_registry

    # ──────────────────────────────────────
    #  marketplace_search
    # ──────────────────────────────────────

    async def _marketplace_search_tool(self, params: Dict) -> str:
        """Search the SableCore Skills Marketplace."""
        query = params.get("query", "")
        category = params.get("category")
        limit = params.get("limit", 10)

        registry = self._get_skill_registry()
        if not registry:
            return "❌ Skills Marketplace is not available. Check gateway configuration."

        try:
            from ..skills_marketplace import SkillCategory

            cat = None
            if category:
                try:
                    cat = SkillCategory(category.lower())
                except ValueError:
                    pass

            skills = await registry.search_skills(
                query=query or None,
                category=cat,
                limit=limit,
            )

            if not skills:
                return f"🏪 No skills found for '{query}'. Try a different search term."

            lines = [f"🏪 **SableCore Skills Marketplace**,  {len(skills)} result(s):\n"]
            for i, skill in enumerate(skills, 1):
                rating = f"⭐ {skill.rating:.1f}" if skill.rating else "No rating"
                lines.append(
                    f"{i}. **{skill.name}** (`{skill.skill_id}`)\n"
                    f"   {skill.description}\n"
                    f"   Category: {skill.category.value if hasattr(skill.category, 'value') else skill.category} | "
                    f"Downloads: {skill.downloads} | {rating}\n"
                    f"   Author: {skill.author} | v{skill.version}"
                )

            lines.append(
                "\n💡 Use `marketplace_info` with the skill ID to see full details, "
                "or `marketplace_install` to install one."
            )
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Marketplace search error: {e}")
            return f"❌ Marketplace search failed: {e}"

    # ──────────────────────────────────────
    #  marketplace_info
    # ──────────────────────────────────────

    async def _marketplace_info_tool(self, params: Dict) -> str:
        """Get detailed info about a marketplace skill."""
        skill_id = params.get("skill_id", "")
        if not skill_id:
            return "❌ Please provide a skill_id."

        registry = self._get_skill_registry()
        if not registry:
            return "❌ Skills Marketplace is not available."

        try:
            skill = await registry.get_skill(skill_id)
            if not skill:
                return f"❌ Skill '{skill_id}' not found in the marketplace."

            info = [
                f"🏪 **{skill.name}** (v{skill.version})",
                f"📝 {skill.description}",
                f"📂 Category: {skill.category.value if hasattr(skill.category, 'value') else skill.category}",
                f"👤 Author: {skill.author}",
                f"📦 Downloads: {skill.downloads}",
                f"⭐ Rating: {skill.rating:.1f}/5 ({skill.reviews_count} reviews)",
                f"📜 License: {skill.license}",
            ]

            if skill.tags:
                info.append(f"🏷️ Tags: {', '.join(skill.tags)}")
            if skill.dependencies:
                info.append(f"📋 Dependencies: {', '.join(skill.dependencies)}")
            if skill.verified:
                info.append("✅ Verified by SableCore team")

            info.append(
                f"\n💡 To install this skill, use `marketplace_install` with skill_id='{skill_id}'"
            )
            return "\n".join(info)

        except Exception as e:
            logger.error(f"Marketplace info error: {e}")
            return f"❌ Failed to get skill info: {e}"

    # ──────────────────────────────────────
    #  marketplace_install
    # ──────────────────────────────────────

    async def _marketplace_install_tool(self, params: Dict) -> str:
        """
        Install a skill from the marketplace.

        This is a HIGH-risk operation that requires user approval
        via the HITL (Human-in-the-Loop) approval gate, unless
        auto-approve mode is enabled.
        """
        skill_id = params.get("skill_id", "")
        if not skill_id:
            return "❌ Please provide a skill_id to install."

        registry = self._get_skill_registry()
        if not registry:
            return "❌ Skills Marketplace is not available."

        try:
            # Get skill info first (for the approval description)
            skill = await registry.get_skill(skill_id)
            skill_name = skill.name if skill else skill_id

            # The actual HITL gate is applied in agent._execute_tool()
            # by the time we get here, the user has already approved.
            result = await registry.install_skill_via_gateway(skill_id)

            return (
                f"✅ **Skill installed successfully!**\n\n"
                f"**{skill_name}** (`{skill_id}`) has been installed.\n"
                f"Server response: {result.get('message', 'OK')}\n\n"
                f"The skill is now available in `opensable/skills/installed/`."
            )

        except RuntimeError as e:
            return f"❌ Gateway error: {e}"
        except Exception as e:
            logger.error(f"Marketplace install error: {e}")
            return f"❌ Installation failed: {e}"

    # ──────────────────────────────────────
    #  marketplace_review
    # ──────────────────────────────────────

    async def _marketplace_review_tool(self, params: Dict) -> str:
        """Post a review on a marketplace skill."""
        skill_id = params.get("skill_id", "")
        rating = params.get("rating", 5)
        title = params.get("title", "")
        content = params.get("content", "")

        if not skill_id:
            return "❌ Please provide a skill_id."
        if not title:
            return "❌ Please provide a review title."
        if not content:
            return "❌ Please provide review content."

        registry = self._get_skill_registry()
        if not registry:
            return "❌ Skills Marketplace is not available."

        try:
            result = await registry.review_skill_via_gateway(
                slug=skill_id,
                rating=max(1, min(5, int(rating))),
                title=title,
                content=content,
            )

            action = "updated" if result.get("updated") else "posted"
            return (
                f"✅ Review {action} for **{skill_id}**!\n"
                f"Rating: {'⭐' * int(rating)} ({rating}/5)\n"
                f"Title: {title}"
            )

        except RuntimeError as e:
            return f"❌ Gateway error: {e}"
        except Exception as e:
            logger.error(f"Marketplace review error: {e}")
            return f"❌ Review failed: {e}"
