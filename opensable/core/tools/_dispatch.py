"""
Schema → internal tool dispatch mapping.
Maps schema_name → (internal_tool_name, argument_mapper).
"""

from typing import Dict, Tuple, Callable, Any

# Passthrough mapper — arguments are forwarded as-is
_p = lambda a: a  # noqa: E731


def _browser_search_mapper(a: Dict[str, Any]) -> Dict[str, Any]:
    return {"action": "search", **a}


def _browser_scrape_mapper(a: Dict[str, Any]) -> Dict[str, Any]:
    return {"action": "scrape", **a}


def _browser_snapshot_mapper(a: Dict[str, Any]) -> Dict[str, Any]:
    return {"action": "snapshot", **a}


SCHEMA_TO_TOOL: Dict[str, Tuple[str, Callable]] = {
    # Browser (remapped action)
    "browser_search": ("browser", _browser_search_mapper),
    "browser_scrape": ("browser", _browser_scrape_mapper),
    "browser_snapshot": ("browser", _browser_snapshot_mapper),
    "browser_action": ("web_action", _p),
    # File / System
    "execute_command": ("execute_command", _p),
    "read_file": ("read_file", _p),
    "write_file": ("write_file", _p),
    "list_directory": ("list_directory", _p),
    "weather": ("weather", _p),
    "calendar": ("calendar", _p),
    "execute_code": ("execute_code", _p),
    "vector_search": ("vector_search", _p),
    "create_skill": ("create_skill", _p),
    "list_skills": ("list_skills", _p),
    "load_tool_details": ("load_tool_details", _p),
    # File ops
    "edit_file": ("edit_file", _p),
    "delete_file": ("delete_file", _p),
    "move_file": ("move_file", _p),
    "search_files": ("search_files", _p),
    "system_info": ("system_info", _p),
    # Desktop control
    "desktop_screenshot": ("desktop_screenshot", _p),
    "desktop_click": ("desktop_click", _p),
    "desktop_type": ("desktop_type", _p),
    "desktop_hotkey": ("desktop_hotkey", _p),
    "desktop_scroll": ("desktop_scroll", _p),
    "desktop_mouse_move": ("desktop_mouse_move", _p),
    # Vision / autonomous
    "screen_analyze": ("screen_analyze", _p),
    "screen_find": ("screen_find", _p),
    "screen_click_on": ("screen_click_on", _p),
    "open_app": ("open_app", _p),
    "open_url": ("open_url", _p),
    "window_list": ("window_list", _p),
    "window_focus": ("window_focus", _p),
    # X / Twitter
    "x_post_tweet": ("x_post_tweet", _p),
    "x_post_thread": ("x_post_thread", _p),
    "x_search": ("x_search", _p),
    "x_get_trends": ("x_get_trends", _p),
    "x_like": ("x_like", _p),
    "x_retweet": ("x_retweet", _p),
    "x_reply": ("x_reply", _p),
    "x_get_user": ("x_get_user", _p),
    "x_get_user_tweets": ("x_get_user_tweets", _p),
    "x_follow": ("x_follow", _p),
    "x_send_dm": ("x_send_dm", _p),
    "x_delete_tweet": ("x_delete_tweet", _p),
    # Grok AI
    "grok_chat": ("grok_chat", _p),
    "grok_analyze_image": ("grok_analyze_image", _p),
    "grok_generate_image": ("grok_generate_image", _p),
    # Documents
    "create_document": ("create_document", _p),
    "create_spreadsheet": ("create_spreadsheet", _p),
    "create_pdf": ("create_pdf", _p),
    "create_presentation": ("create_presentation", _p),
    "read_document": ("read_document", _p),
    "open_document": ("open_document", _p),
    "write_in_writer": ("write_in_writer", _p),
    # Email
    "email_send": ("email_send", _p),
    "email_read": ("email_read", _p),
    # Calendar (Google)
    "calendar_list_events": ("calendar_list_events", _p),
    "calendar_add_event": ("calendar_add_event", _p),
    "calendar_delete_event": ("calendar_delete_event", _p),
    # Clipboard
    "clipboard_copy": ("clipboard_copy", _p),
    "clipboard_paste": ("clipboard_paste", _p),
    # OCR
    "ocr_extract": ("ocr_extract", _p),
    # Trading
    "trading_portfolio": ("trading_portfolio", _p),
    "trading_price": ("trading_price", _p),
    "trading_analyze": ("trading_analyze", _p),
    "trading_place_trade": ("trading_place_trade", _p),
    "trading_cancel_order": ("trading_cancel_order", _p),
    "trading_history": ("trading_history", _p),
    "trading_signals": ("trading_signals", _p),
    "trading_start_scan": ("trading_start_scan", _p),
    "trading_stop_scan": ("trading_stop_scan", _p),
    "trading_risk_status": ("trading_risk_status", _p),
    # Marketplace
    "marketplace_search": ("marketplace_search", _p),
    "marketplace_info": ("marketplace_info", _p),
    "marketplace_install": ("marketplace_install", _p),
    "marketplace_review": ("marketplace_review", _p),
    # Mobile
    "phone_notify": ("phone_notify", _p),
    "phone_reminder": ("phone_reminder", _p),
    "phone_geofence": ("phone_geofence", _p),
    "phone_location": ("phone_location", _p),
    "phone_device": ("phone_device", _p),
    # Instagram
    "ig_upload_photo": ("ig_upload_photo", _p),
    "ig_upload_reel": ("ig_upload_reel", _p),
    "ig_upload_story": ("ig_upload_story", _p),
    "ig_search_users": ("ig_search_users", _p),
    "ig_search_hashtags": ("ig_search_hashtags", _p),
    "ig_get_user_info": ("ig_get_user_info", _p),
    "ig_get_timeline": ("ig_get_timeline", _p),
    "ig_like_media": ("ig_like_media", _p),
    "ig_comment": ("ig_comment", _p),
    "ig_follow_user": ("ig_follow_user", _p),
    "ig_send_dm": ("ig_send_dm", _p),
    "ig_get_media_comments": ("ig_get_media_comments", _p),
    # Facebook
    "fb_post": ("fb_post", _p),
    "fb_upload_photo": ("fb_upload_photo", _p),
    "fb_get_feed": ("fb_get_feed", _p),
    "fb_like_post": ("fb_like_post", _p),
    "fb_comment": ("fb_comment", _p),
    "fb_get_profile": ("fb_get_profile", _p),
    "fb_search": ("fb_search", _p),
    # LinkedIn
    "linkedin_get_profile": ("linkedin_get_profile", _p),
    "linkedin_search_people": ("linkedin_search_people", _p),
    "linkedin_search_companies": ("linkedin_search_companies", _p),
    "linkedin_search_jobs": ("linkedin_search_jobs", _p),
    "linkedin_post_update": ("linkedin_post_update", _p),
    "linkedin_send_message": ("linkedin_send_message", _p),
    "linkedin_send_connection": ("linkedin_send_connection", _p),
    "linkedin_get_feed": ("linkedin_get_feed", _p),
    # TikTok
    "tiktok_trending": ("tiktok_trending", _p),
    "tiktok_search_videos": ("tiktok_search_videos", _p),
    "tiktok_search_users": ("tiktok_search_users", _p),
    "tiktok_get_user_info": ("tiktok_get_user_info", _p),
    "tiktok_get_user_videos": ("tiktok_get_user_videos", _p),
    "tiktok_get_hashtag_videos": ("tiktok_get_hashtag_videos", _p),
    # YouTube
    "yt_search_videos": ("yt_search_videos", _p),
    "yt_search_channels": ("yt_search_channels", _p),
    "yt_get_channel": ("yt_get_channel", _p),
    "yt_get_channel_videos": ("yt_get_channel_videos", _p),
    "yt_get_video": ("yt_get_video", _p),
    "yt_get_comments": ("yt_get_comments", _p),
    "yt_comment": ("yt_comment", _p),
    "yt_get_playlist": ("yt_get_playlist", _p),
    "yt_rate_video": ("yt_rate_video", _p),
    "yt_subscribe": ("yt_subscribe", _p),
    "yt_trending": ("yt_trending", _p),
    "yt_upload_video": ("yt_upload_video", _p),
}
