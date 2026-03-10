"""
Social media tools,  X (Twitter), Grok, Instagram, Facebook, LinkedIn, TikTok, YouTube

⚠️  These integrations are provided for TESTING AND EDUCATIONAL PURPOSES ONLY.
Users are responsible for complying with each platform's Terms of Service.
Automated actions (posting, liking, following, DMs) may violate platform rules
if used outside of approved API access or without proper authorization.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class SocialToolsMixin:
    """Mixin providing social media tools,  x (twitter), grok, instagram, facebook, linkedin, tiktok, youtube tool implementations."""

    # ========== X (TWITTER) TOOLS ==========

    async def _x_post_tweet_tool(self, params: Dict) -> str:
        """Post a tweet on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
        text = params.get("text", "")
        media_paths = params.get("media_paths")
        reply_to = params.get("reply_to")
        result = await self.x_skill.post_tweet(text, media_paths=media_paths, reply_to=reply_to)
        if result.get("success"):
            url = result.get("url", "")
            return f"✅ Tweet posted!\n📝 {text[:100]}{'...' if len(text)>100 else ''}\n🔗 {url}"
        return f"❌ Failed to post tweet: {result.get('error')}"

    async def _x_post_thread_tool(self, params: Dict) -> str:
        """Post a thread on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
        tweets = params.get("tweets", [])
        if not tweets:
            return "❌ No tweets provided for thread"
        result = await self.x_skill.post_thread(tweets)
        if result.get("success"):
            url = result.get("thread_url", "")
            return f"✅ Thread posted ({result['thread_length']} tweets)\n🔗 {url}"
        return f"❌ Thread failed: {result.get('error')}"

    async def _x_search_tool(self, params: Dict) -> str:
        """Search tweets on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        query = params.get("query", "")
        search_type = params.get("search_type", "Latest")
        count = params.get("count", 10)
        result = await self.x_skill.search_tweets(query, search_type=search_type, count=count)
        if result.get("success"):
            tweets = result.get("tweets", [])
            if not tweets:
                return f"🔍 No tweets found for '{query}'"
            lines = []
            for t in tweets:
                lines.append(f"  @{t.get('username', '?')}: {t.get('text', '')[:120]}")
                lines.append(f"    ❤️ {t.get('likes', 0)} | 🔁 {t.get('retweets', 0)}")
            return f"🔍 Search results for '{query}' ({len(tweets)}):\n" + "\n".join(lines)
        return f"❌ Search failed: {result.get('error')}"

    async def _x_get_trends_tool(self, params: Dict) -> str:
        """Get trending topics on X"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        category = params.get("category", "trending")
        result = await self.x_skill.get_trends(category)
        if result.get("success"):
            trends = result.get("trends", [])
            lines = [f"  {i+1}. {t.get('name', '?')}" for i, t in enumerate(trends)]
            return f"📈 Trending on X ({category}):\n" + "\n".join(lines)
        return f"❌ Trends failed: {result.get('error')}"

    async def _x_like_tool(self, params: Dict) -> str:
        """Like a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.like_tweet(params.get("tweet_id", ""))
        return f"❤️ Tweet liked!" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_retweet_tool(self, params: Dict) -> str:
        """Retweet a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.retweet(params.get("tweet_id", ""))
        return f"🔁 Retweeted!" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_reply_tool(self, params: Dict) -> str:
        """Reply to a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.reply(params.get("tweet_id", ""), params.get("text", ""))
        if result.get("success"):
            return f"💬 Reply posted! {result.get('url', '')}"
        return f"❌ Reply failed: {result.get('error')}"

    async def _x_get_user_tool(self, params: Dict) -> str:
        """Get user profile"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.get_user(params.get("username", ""))
        if result.get("success"):
            return (
                f"👤 @{result.get('username')}\n"
                f"   Name: {result.get('name')}\n"
                f"   Bio: {result.get('bio', 'N/A')}\n"
                f"   Followers: {result.get('followers', 0):,}\n"
                f"   Following: {result.get('following', 0):,}\n"
                f"   Tweets: {result.get('tweets_count', 0):,}"
            )
        return f"❌ {result.get('error')}"

    async def _x_get_user_tweets_tool(self, params: Dict) -> str:
        """Get a user's tweets"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        username = params.get("username", "")
        tweet_type = params.get("tweet_type", "Tweets")
        count = params.get("count", 10)
        result = await self.x_skill.get_user_tweets(username, tweet_type=tweet_type, count=count)
        if result.get("success"):
            tweets = result.get("tweets", [])
            lines = [f"  - {t.get('text', '')[:140]}" for t in tweets]
            return f"📜 @{username} tweets ({len(tweets)}):\n" + "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _x_follow_tool(self, params: Dict) -> str:
        """Follow a user"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.follow_user(params.get("username", ""))
        return f"✅ Followed @{params.get('username')}" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_send_dm_tool(self, params: Dict) -> str:
        """Send a DM"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.send_dm(params.get("user_id", ""), params.get("text", ""))
        return f"✉️ DM sent!" if result.get("success") else f"❌ {result.get('error')}"

    async def _x_delete_tweet_tool(self, params: Dict) -> str:
        """Delete a tweet"""
        if not self.x_skill or not self.x_skill.is_available():
            return "❌ X skill not initialized."
        result = await self.x_skill.delete_tweet(params.get("tweet_id", ""))
        return f"🗑️ Tweet deleted!" if result.get("success") else f"❌ {result.get('error')}"

    # ========== GROK AI TOOLS ==========

    async def _grok_chat_tool(self, params: Dict) -> str:
        """Chat with Grok AI"""
        if not self.grok_skill:
            return "❌ Grok skill not initialized. Set X_USERNAME, X_EMAIL, X_PASSWORD in .env"
        message = params.get("message", "")
        conversation_id = params.get("conversation_id")
        result = await self.grok_skill.chat(message, conversation_id=conversation_id)
        if result.get("success"):
            conv_id = result.get("conversation_id", "")
            return f"🤖 **Grok**: {result['response']}\n\n_Conversation: {conv_id}_"
        return f"❌ Grok error: {result.get('error')}"

    async def _grok_analyze_image_tool(self, params: Dict) -> str:
        """Analyze images with Grok"""
        if not self.grok_skill:
            return "❌ Grok skill not initialized."
        image_paths = params.get("image_paths", [])
        prompt = params.get("prompt", "Please describe these images in detail.")
        result = await self.grok_skill.analyze_image(image_paths, prompt)
        if result.get("success"):
            return f"👁️ **Grok Vision**: {result['response']}"
        return f"❌ Grok image analysis error: {result.get('error')}"

    async def _grok_generate_image_tool(self, params: Dict) -> str:
        """Generate images with Grok"""
        if not self.grok_skill:
            return "❌ Grok skill not initialized."
        prompt = params.get("prompt", "")
        save_path = params.get("save_path")
        result = await self.grok_skill.generate_image(prompt, save_path=save_path)
        if result.get("success"):
            images = result.get("images", [])
            return f"🎨 **Grok Image**: Generated {len(images)} image(s)\n" + "\n".join(f"  📁 {p}" for p in images)
        return f"❌ Grok image generation error: {result.get('error')}"

    # ========== INSTAGRAM TOOLS ==========

    async def _ig_upload_photo_tool(self, params: Dict) -> str:
        """Upload a photo to Instagram"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized. Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env"
        result = await self.instagram_skill.upload_photo(
            path=params.get("photo_path", ""),
            caption=params.get("caption", ""),
        )
        if result.get("success"):
            return f"📸 Photo uploaded to Instagram! Media ID: {result.get('media_id', 'N/A')}"
        return f"❌ Instagram upload error: {result.get('error')}"

    async def _ig_upload_reel_tool(self, params: Dict) -> str:
        """Upload a reel to Instagram"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized. Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env"
        result = await self.instagram_skill.upload_reel(
            video_path=params.get("video_path", ""),
            caption=params.get("caption", ""),
        )
        if result.get("success"):
            return f"🎬 Reel uploaded to Instagram! Media ID: {result.get('media_id', 'N/A')}"
        return f"❌ Instagram reel upload error: {result.get('error')}"

    async def _ig_upload_story_tool(self, params: Dict) -> str:
        """Upload a story to Instagram"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        file_path = params.get("file_path", "")
        caption = params.get("caption", "")
        # Detect if video or photo based on extension
        if file_path.lower().endswith((".mp4", ".mov", ".avi")):
            result = await self.instagram_skill.upload_story(video_path=file_path, caption=caption)
        else:
            result = await self.instagram_skill.upload_story(photo_path=file_path, caption=caption)
        if result.get("success"):
            return f"📖 Story uploaded to Instagram! Media ID: {result.get('media_id', 'N/A')}"
        return f"❌ Instagram story upload error: {result.get('error')}"

    async def _ig_search_users_tool(self, params: Dict) -> str:
        """Search Instagram users"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.search_users(
            query=params.get("query", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            users = result.get("users", [])
            if not users:
                return "🔍 No Instagram users found."
            lines = [f"🔍 Found {len(users)} Instagram user(s):"]
            for u in users[:10]:
                lines.append(f"  • @{u.get('username', '?')},  {u.get('full_name', '')} (followers: {u.get('follower_count', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _ig_search_hashtags_tool(self, params: Dict) -> str:
        """Search Instagram hashtags"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.search_hashtags(
            query=params.get("query", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            tags = result.get("hashtags", [])
            if not tags:
                return "🔍 No hashtags found."
            lines = [f"#️⃣ Found {len(tags)} hashtag(s):"]
            for t in tags[:10]:
                lines.append(f"  • #{t.get('name', '?')},  {t.get('media_count', '?')} posts")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _ig_get_user_info_tool(self, params: Dict) -> str:
        """Get Instagram user info"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.get_user_info(username=params.get("username", ""))
        if result.get("success"):
            u = result.get("user", {})
            return (
                f"👤 **@{u.get('username', '?')}** ({u.get('full_name', '')})\n"
                f"  Bio: {u.get('biography', 'N/A')}\n"
                f"  Followers: {u.get('follower_count', '?')} | Following: {u.get('following_count', '?')}\n"
                f"  Posts: {u.get('media_count', '?')} | Verified: {'✅' if u.get('is_verified') else '❌'}"
            )
        return f"❌ {result.get('error')}"

    async def _ig_get_timeline_tool(self, params: Dict) -> str:
        """Get Instagram timeline"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.get_timeline(count=params.get("count", 20))
        if result.get("success"):
            posts = result.get("posts", [])
            if not posts:
                return "📱 No timeline posts found."
            lines = [f"📱 Timeline ({len(posts)} posts):"]
            for p in posts[:10]:
                lines.append(f"  • @{p.get('username', '?')}: {(p.get('caption', '') or '')[:80]}...")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _ig_like_media_tool(self, params: Dict) -> str:
        """Like an Instagram post"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.like_media(media_id=params.get("media_id", ""))
        return "❤️ Post liked!" if result.get("success") else f"❌ {result.get('error')}"

    async def _ig_comment_tool(self, params: Dict) -> str:
        """Comment on an Instagram post"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.comment(
            media_id=params.get("media_id", ""),
            text=params.get("text", ""),
        )
        if result.get("success"):
            return f"💬 Comment posted! Comment ID: {result.get('comment_id', 'N/A')}"
        return f"❌ {result.get('error')}"

    async def _ig_follow_user_tool(self, params: Dict) -> str:
        """Follow an Instagram user"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.follow_user(username=params.get("username", ""))
        return f"✅ Now following @{params.get('username')}!" if result.get("success") else f"❌ {result.get('error')}"

    async def _ig_send_dm_tool(self, params: Dict) -> str:
        """Send Instagram DM"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.send_dm(
            username=params.get("username", ""),
            text=params.get("text", ""),
        )
        return "✉️ DM sent!" if result.get("success") else f"❌ {result.get('error')}"

    async def _ig_get_media_comments_tool(self, params: Dict) -> str:
        """Get comments on an Instagram post"""
        if not self.instagram_skill:
            return "❌ Instagram skill not initialized."
        result = await self.instagram_skill.get_media_comments(
            media_id=params.get("media_id", ""),
            count=params.get("count", 20),
        )
        if result.get("success"):
            comments = result.get("comments", [])
            if not comments:
                return "💬 No comments found."
            lines = [f"💬 {len(comments)} comment(s):"]
            for c in comments[:15]:
                lines.append(f"  • @{c.get('username', '?')}: {(c.get('text', '') or '')[:100]}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    # ========== FACEBOOK TOOLS ==========

    async def _fb_post_tool(self, params: Dict) -> str:
        """Post to Facebook"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized. Set FACEBOOK_ACCESS_TOKEN in .env"
        result = await self.facebook_skill.post(
            message=params.get("message", ""),
            link=params.get("link"),
        )
        if result.get("success"):
            return f"📘 Posted to Facebook! Post ID: {result.get('post_id', 'N/A')}"
        return f"❌ Facebook post error: {result.get('error')}"

    async def _fb_upload_photo_tool(self, params: Dict) -> str:
        """Upload photo to Facebook"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized."
        result = await self.facebook_skill.upload_photo(
            photo_path=params.get("photo_path", ""),
            caption=params.get("caption", ""),
        )
        if result.get("success"):
            return f"📸 Photo uploaded to Facebook! Post ID: {result.get('post_id', 'N/A')}"
        return f"❌ {result.get('error')}"

    async def _fb_get_feed_tool(self, params: Dict) -> str:
        """Get Facebook feed"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized."
        result = await self.facebook_skill.get_feed(count=params.get("count", 10))
        if result.get("success"):
            posts = result.get("posts", [])
            if not posts:
                return "📘 No feed posts found."
            lines = [f"📘 Facebook Feed ({len(posts)} posts):"]
            for p in posts[:10]:
                msg = (p.get("message", "") or "")[:80]
                lines.append(f"  • [{p.get('id', '?')}] {msg}{'...' if len(msg) >= 80 else ''}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _fb_like_post_tool(self, params: Dict) -> str:
        """Like a Facebook post"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized."
        result = await self.facebook_skill.like_post(post_id=params.get("post_id", ""))
        return "👍 Post liked!" if result.get("success") else f"❌ {result.get('error')}"

    async def _fb_comment_tool(self, params: Dict) -> str:
        """Comment on a Facebook post"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized."
        result = await self.facebook_skill.comment_on_post(
            post_id=params.get("post_id", ""),
            message=params.get("message", ""),
        )
        if result.get("success"):
            return f"💬 Comment posted! Comment ID: {result.get('comment_id', 'N/A')}"
        return f"❌ {result.get('error')}"

    async def _fb_get_profile_tool(self, params: Dict) -> str:
        """Get Facebook profile"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized."
        result = await self.facebook_skill.get_profile(user_id=params.get("user_id", "me"))
        if result.get("success"):
            p = result.get("profile", {})
            return (
                f"👤 **{p.get('name', '?')}**\n"
                f"  ID: {p.get('id', '?')}\n"
                f"  Link: {p.get('link', 'N/A')}"
            )
        return f"❌ {result.get('error')}"

    async def _fb_search_tool(self, params: Dict) -> str:
        """Search Facebook"""
        if not self.facebook_skill:
            return "❌ Facebook skill not initialized."
        result = await self.facebook_skill.search(
            query=params.get("query", ""),
            search_type=params.get("search_type", "page"),
            count=params.get("count", 10),
        )
        if result.get("success"):
            results = result.get("results", [])
            if not results:
                return "🔍 No results found."
            lines = [f"🔍 Facebook search ({len(results)} results):"]
            for r in results[:10]:
                lines.append(f"  • {r.get('name', '?')} (ID: {r.get('id', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    # ========== LINKEDIN TOOLS ==========

    async def _linkedin_get_profile_tool(self, params: Dict) -> str:
        """Get LinkedIn profile"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized. Set LINKEDIN_USERNAME and LINKEDIN_PASSWORD in .env"
        result = await self.linkedin_skill.get_profile(username=params.get("username", ""))
        if result.get("success"):
            p = result.get("profile", {})
            return (
                f"👤 **{p.get('first_name', '')} {p.get('last_name', '')}**\n"
                f"  Headline: {p.get('headline', 'N/A')}\n"
                f"  Location: {p.get('location', 'N/A')}\n"
                f"  Industry: {p.get('industry', 'N/A')}\n"
                f"  Summary: {(p.get('summary', '') or '')[:200]}"
            )
        return f"❌ {result.get('error')}"

    async def _linkedin_search_people_tool(self, params: Dict) -> str:
        """Search LinkedIn people"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.search_people(
            keywords=params.get("keywords", ""),
            limit=params.get("limit", 10),
        )
        if result.get("success"):
            people = result.get("people", [])
            if not people:
                return "🔍 No people found."
            lines = [f"🔍 LinkedIn People ({len(people)} results):"]
            for p in people[:10]:
                lines.append(f"  • {p.get('name', '?')},  {p.get('headline', 'N/A')}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _linkedin_search_companies_tool(self, params: Dict) -> str:
        """Search LinkedIn companies"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.search_companies(
            keywords=params.get("keywords", ""),
            limit=params.get("limit", 10),
        )
        if result.get("success"):
            companies = result.get("companies", [])
            if not companies:
                return "🔍 No companies found."
            lines = [f"🏢 LinkedIn Companies ({len(companies)} results):"]
            for c in companies[:10]:
                lines.append(f"  • {c.get('name', '?')},  {c.get('industry', 'N/A')}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _linkedin_search_jobs_tool(self, params: Dict) -> str:
        """Search LinkedIn jobs"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.search_jobs(
            keywords=params.get("keywords", ""),
            location=params.get("location"),
            limit=params.get("limit", 10),
        )
        if result.get("success"):
            jobs = result.get("jobs", [])
            if not jobs:
                return "🔍 No jobs found."
            lines = [f"💼 LinkedIn Jobs ({len(jobs)} results):"]
            for j in jobs[:10]:
                lines.append(f"  • {j.get('title', '?')} at {j.get('company', '?')},  {j.get('location', 'N/A')}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _linkedin_post_update_tool(self, params: Dict) -> str:
        """Post an update on LinkedIn"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.post_update(text=params.get("text", ""))
        if result.get("success"):
            return f"📝 Posted to LinkedIn! Post ID: {result.get('post_id', 'N/A')}"
        return f"❌ {result.get('error')}"

    async def _linkedin_send_message_tool(self, params: Dict) -> str:
        """Send a LinkedIn message"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.send_message(
            profile_id=params.get("profile_id", ""),
            message=params.get("message", ""),
        )
        return "✉️ LinkedIn message sent!" if result.get("success") else f"❌ {result.get('error')}"

    async def _linkedin_send_connection_tool(self, params: Dict) -> str:
        """Send LinkedIn connection request"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.send_connection_request(
            profile_id=params.get("profile_id", ""),
            message=params.get("message", ""),
        )
        return "🤝 Connection request sent!" if result.get("success") else f"❌ {result.get('error')}"

    async def _linkedin_get_feed_tool(self, params: Dict) -> str:
        """Get LinkedIn feed"""
        if not self.linkedin_skill:
            return "❌ LinkedIn skill not initialized."
        result = await self.linkedin_skill.get_feed_posts(count=params.get("count", 10))
        if result.get("success"):
            posts = result.get("posts", [])
            if not posts:
                return "📝 No feed posts found."
            lines = [f"📝 LinkedIn Feed ({len(posts)} posts):"]
            for p in posts[:10]:
                text = (p.get("text", "") or "")[:80]
                lines.append(f"  • {p.get('author', '?')}: {text}{'...' if len(text) >= 80 else ''}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    # ========== TIKTOK TOOLS (READ-ONLY) ==========

    async def _tiktok_trending_tool(self, params: Dict) -> str:
        """Get trending TikTok videos"""
        if not self.tiktok_skill:
            return "❌ TikTok skill not initialized. Requires TikTokApi + Playwright. Optionally set TIKTOK_MS_TOKEN in .env"
        result = await self.tiktok_skill.get_trending_videos(count=params.get("count", 10))
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return "📱 No trending videos found."
            lines = [f"🔥 TikTok Trending ({len(videos)} videos):"]
            for v in videos[:10]:
                lines.append(f"  • @{v.get('author', '?')}: {(v.get('desc', '') or '')[:60]} (❤️ {v.get('likes', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _tiktok_search_videos_tool(self, params: Dict) -> str:
        """Search TikTok videos"""
        if not self.tiktok_skill:
            return "❌ TikTok skill not initialized."
        result = await self.tiktok_skill.search_videos(
            query=params.get("query", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return "🔍 No videos found."
            lines = [f"🔍 TikTok Videos ({len(videos)} results):"]
            for v in videos[:10]:
                lines.append(f"  • @{v.get('author', '?')}: {(v.get('desc', '') or '')[:60]} (❤️ {v.get('likes', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _tiktok_search_users_tool(self, params: Dict) -> str:
        """Search TikTok users"""
        if not self.tiktok_skill:
            return "❌ TikTok skill not initialized."
        result = await self.tiktok_skill.search_users(
            query=params.get("query", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            users = result.get("users", [])
            if not users:
                return "🔍 No users found."
            lines = [f"🔍 TikTok Users ({len(users)} results):"]
            for u in users[:10]:
                lines.append(f"  • @{u.get('username', '?')},  {u.get('nickname', '')} (followers: {u.get('follower_count', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _tiktok_get_user_info_tool(self, params: Dict) -> str:
        """Get TikTok user info"""
        if not self.tiktok_skill:
            return "❌ TikTok skill not initialized."
        result = await self.tiktok_skill.get_user_info(username=params.get("username", ""))
        if result.get("success"):
            u = result.get("user", {})
            return (
                f"👤 **@{u.get('username', '?')}** ({u.get('nickname', '')})\n"
                f"  Bio: {(u.get('bio', '') or '')[:150]}\n"
                f"  Followers: {u.get('follower_count', '?')} | Following: {u.get('following_count', '?')}\n"
                f"  Likes: {u.get('likes_count', '?')} | Videos: {u.get('video_count', '?')}\n"
                f"  Verified: {'✅' if u.get('verified') else '❌'}"
            )
        return f"❌ {result.get('error')}"

    async def _tiktok_get_user_videos_tool(self, params: Dict) -> str:
        """Get TikTok user videos"""
        if not self.tiktok_skill:
            return "❌ TikTok skill not initialized."
        result = await self.tiktok_skill.get_user_videos(
            username=params.get("username", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return "📱 No videos found for this user."
            lines = [f"📱 @{params.get('username')} Videos ({len(videos)}):"]
            for v in videos[:10]:
                lines.append(f"  • {(v.get('desc', '') or '')[:60]} (❤️ {v.get('likes', '?')} | 👀 {v.get('views', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _tiktok_get_hashtag_videos_tool(self, params: Dict) -> str:
        """Get TikTok hashtag videos"""
        if not self.tiktok_skill:
            return "❌ TikTok skill not initialized."
        result = await self.tiktok_skill.get_hashtag_videos(
            hashtag=params.get("hashtag", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return f"#️⃣ No videos found for #{params.get('hashtag')}."
            lines = [f"#️⃣ #{params.get('hashtag')} ({len(videos)} videos):"]
            for v in videos[:10]:
                lines.append(f"  • @{v.get('author', '?')}: {(v.get('desc', '') or '')[:60]} (❤️ {v.get('likes', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    # ========== YOUTUBE TOOLS ==========

    async def _yt_search_videos_tool(self, params: Dict) -> str:
        """Search YouTube videos"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized. Set YOUTUBE_API_KEY in .env"
        result = await self.youtube_skill.search_videos(
            query=params.get("query", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return "🔍 No YouTube videos found."
            lines = [f"🔍 YouTube Videos ({len(videos)} results):"]
            for v in videos[:10]:
                lines.append(f"  • [{v.get('title', '?')}]({v.get('url', '')}),  {v.get('channel_title', '?')}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _yt_search_channels_tool(self, params: Dict) -> str:
        """Search YouTube channels"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.search_channels(
            query=params.get("query", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            channels = result.get("channels", [])
            if not channels:
                return "🔍 No channels found."
            lines = [f"🔍 YouTube Channels ({len(channels)} results):"]
            for c in channels[:10]:
                lines.append(f"  • {c.get('title', '?')},  {(c.get('description', '') or '')[:60]}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _yt_get_channel_tool(self, params: Dict) -> str:
        """Get YouTube channel info"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.get_channel_info(channel_id=params.get("channel_id", ""))
        if result.get("success"):
            ch = result.get("channel", {})
            return (
                f"📺 **{ch.get('title', '?')}**\n"
                f"  Subscribers: {ch.get('subscriber_count', '?')} | Videos: {ch.get('video_count', '?')}\n"
                f"  Views: {ch.get('view_count', '?')}\n"
                f"  Country: {ch.get('country', 'N/A')}\n"
                f"  URL: https://youtube.com/channel/{ch.get('id', '')}\n"
                f"  Description: {(ch.get('description', '') or '')[:200]}"
            )
        return f"❌ {result.get('error')}"

    async def _yt_get_channel_videos_tool(self, params: Dict) -> str:
        """Get recent videos from a YouTube channel"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.get_channel_videos(
            channel_id=params.get("channel_id", ""),
            count=params.get("count", 10),
        )
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return "📺 No videos found for this channel."
            lines = [f"📺 Channel Videos ({len(videos)}):"]
            for v in videos[:10]:
                lines.append(f"  • [{v.get('title', '?')}]({v.get('url', '')}),  {v.get('published_at', '')[:10]}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _yt_get_video_tool(self, params: Dict) -> str:
        """Get YouTube video info"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.get_video_info(video_id=params.get("video_id", ""))
        if result.get("success"):
            v = result.get("video", {})
            return (
                f"🎬 **{v.get('title', '?')}**\n"
                f"  Channel: {v.get('channel_title', '?')}\n"
                f"  Views: {v.get('view_count', '?')} | Likes: {v.get('like_count', '?')} | Comments: {v.get('comment_count', '?')}\n"
                f"  Duration: {v.get('duration', '?')}\n"
                f"  Published: {v.get('published_at', '')[:10]}\n"
                f"  URL: {v.get('url', '')}\n"
                f"  Tags: {', '.join(v.get('tags', [])[:5])}"
            )
        return f"❌ {result.get('error')}"

    async def _yt_get_comments_tool(self, params: Dict) -> str:
        """Get YouTube video comments"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.get_video_comments(
            video_id=params.get("video_id", ""),
            count=params.get("count", 20),
        )
        if result.get("success"):
            comments = result.get("comments", [])
            if not comments:
                return "💬 No comments found."
            lines = [f"💬 YouTube Comments ({len(comments)}):"]
            for c in comments[:15]:
                lines.append(f"  • **{c.get('author', '?')}** (👍 {c.get('like_count', 0)}): {(c.get('text', '') or '')[:100]}")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _yt_comment_tool(self, params: Dict) -> str:
        """Post a comment on a YouTube video"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.comment_on_video(
            video_id=params.get("video_id", ""),
            text=params.get("text", ""),
        )
        if result.get("success"):
            return f"💬 Comment posted! Comment ID: {result.get('comment_id', 'N/A')}"
        return f"❌ {result.get('error')}"

    async def _yt_get_playlist_tool(self, params: Dict) -> str:
        """Get YouTube playlist items"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.get_playlist_items(
            playlist_id=params.get("playlist_id", ""),
            count=params.get("count", 20),
        )
        if result.get("success"):
            items = result.get("items", [])
            if not items:
                return "📋 No playlist items found."
            lines = [f"📋 Playlist ({len(items)} items):"]
            for i in items[:15]:
                lines.append(f"  {i.get('position', 0)+1}. [{i.get('title', '?')}]({i.get('url', '')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _yt_rate_video_tool(self, params: Dict) -> str:
        """Like/dislike a YouTube video"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        rating = params.get("rating", "like")
        result = await self.youtube_skill.rate_video(
            video_id=params.get("video_id", ""),
            rating=rating,
        )
        emoji = {"like": "👍", "dislike": "👎", "none": "🚫"}.get(rating, "✅")
        return f"{emoji} Video rated: {rating}" if result.get("success") else f"❌ {result.get('error')}"

    async def _yt_subscribe_tool(self, params: Dict) -> str:
        """Subscribe to a YouTube channel"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.subscribe(channel_id=params.get("channel_id", ""))
        return "🔔 Subscribed!" if result.get("success") else f"❌ {result.get('error')}"

    async def _yt_trending_tool(self, params: Dict) -> str:
        """Get trending YouTube videos"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.get_trending(
            region_code=params.get("region_code", "US"),
            count=params.get("count", 10),
        )
        if result.get("success"):
            videos = result.get("videos", [])
            if not videos:
                return "🔥 No trending videos found."
            lines = [f"🔥 YouTube Trending ({len(videos)} videos):"]
            for v in videos[:10]:
                lines.append(f"  • [{v.get('title', '?')}]({v.get('url', '')}),  {v.get('channel_title', '?')} (👀 {v.get('view_count', '?')})")
            return "\n".join(lines)
        return f"❌ {result.get('error')}"

    async def _yt_upload_video_tool(self, params: Dict) -> str:
        """Upload a video to YouTube"""
        if not self.youtube_skill:
            return "❌ YouTube skill not initialized."
        result = await self.youtube_skill.upload_video(
            file_path=params.get("file_path", ""),
            title=params.get("title", "Uploaded via Open-Sable"),
            description=params.get("description", ""),
            tags=params.get("tags"),
            privacy=params.get("privacy", "private"),
        )
        if result.get("success"):
            return f"📤 Video uploaded to YouTube!\n  URL: {result.get('url', 'N/A')}\n  Video ID: {result.get('video_id', 'N/A')}"
        return f"❌ {result.get('error')}"

