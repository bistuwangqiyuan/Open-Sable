#!/usr/bin/env python3
"""Create the job_tracker dynamic skill directly (bypassing LLM generation)."""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

JOB_TRACKER_CODE = r'''
"""
Job Application Tracker - Dynamic Skill
Tracks job applications with SQLite persistence.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(globals().get("__skill_data_dir__", "."))
DB_PATH = str(DATA_DIR / "job_tracker.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "job_add",
            "description": "Save a new job application to the tracker",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "position": {"type": "string", "description": "Job title/position"},
                    "url": {"type": "string", "description": "Job listing URL (optional)"},
                    "status": {
                        "type": "string",
                        "description": "Application status",
                        "enum": ["applied", "screening", "interview", "offer", "rejected"],
                    },
                    "notes": {"type": "string", "description": "Additional notes (optional)"},
                },
                "required": ["company", "position"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "job_search",
            "description": "Search job applications by company name or position keyword",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword (matches company or position)"},
                    "status": {
                        "type": "string",
                        "description": "Filter by status (optional)",
                        "enum": ["applied", "screening", "interview", "offer", "rejected"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "job_update_status",
            "description": "Update the status of a job application",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "integer", "description": "Job application ID"},
                    "status": {
                        "type": "string",
                        "description": "New status",
                        "enum": ["applied", "screening", "interview", "offer", "rejected"],
                    },
                    "notes": {"type": "string", "description": "Optional note about the update"},
                },
                "required": ["job_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "job_summary",
            "description": "Get a summary of all job applications - counts by status, recent activity, and pending items",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

TOOL_PERMISSIONS = {
    "job_add": "dynamic_skill",
    "job_search": "dynamic_skill",
    "job_update_status": "dynamic_skill",
    "job_summary": "dynamic_skill",
}


async def initialize():
    """Create the job applications table if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company     TEXT NOT NULL,
            position    TEXT NOT NULL,
            url         TEXT DEFAULT '',
            status      TEXT DEFAULT 'applied',
            date_applied TEXT,
            notes       TEXT DEFAULT '',
            created_at  TEXT,
            updated_at  TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_app_company ON applications(company)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status)")
    conn.commit()
    conn.close()


async def handle_job_add(params):
    """Add a new job application."""
    company = params.get("company", "")
    position = params.get("position", "")
    url = params.get("url", "")
    status = params.get("status", "applied")
    notes = params.get("notes", "")
    now = datetime.utcnow().isoformat()
    date_applied = params.get("date_applied", now[:10])

    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO applications (company, position, url, status, date_applied, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (company, position, url, status, date_applied, notes, now, now),
    )
    job_id = cur.lastrowid
    conn.commit()
    conn.close()

    return json.dumps({
        "success": True,
        "job_id": job_id,
        "message": f"Added: {position} at {company} (status: {status})",
    })


async def handle_job_search(params):
    """Search applications by company or position."""
    query = params.get("query", "")
    status_filter = params.get("status", "")

    conn = _get_db()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM applications WHERE (company LIKE ? OR position LIKE ?) AND status = ? ORDER BY updated_at DESC",
            (f"%{query}%", f"%{query}%", status_filter),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM applications WHERE company LIKE ? OR position LIKE ? ORDER BY updated_at DESC",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    conn.close()

    results = [dict(r) for r in rows]
    return json.dumps({"count": len(results), "applications": results})


async def handle_job_update_status(params):
    """Update application status."""
    job_id = params.get("job_id")
    new_status = params.get("status", "")
    notes = params.get("notes", "")
    now = datetime.utcnow().isoformat()

    conn = _get_db()
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (job_id,)).fetchone()
    if not row:
        conn.close()
        return json.dumps({"success": False, "error": f"Job #{job_id} not found"})

    old_status = row["status"]
    update_notes = row["notes"]
    if notes:
        sep = "\n" if update_notes else ""
        update_notes = f"{update_notes}{sep}[{now[:10]}] {old_status} -> {new_status}: {notes}"

    conn.execute(
        "UPDATE applications SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
        (new_status, update_notes, now, job_id),
    )
    conn.commit()
    conn.close()

    return json.dumps({
        "success": True,
        "message": f"Job #{job_id} ({row['company']} - {row['position']}): {old_status} -> {new_status}",
    })


async def handle_job_summary(params):
    """Return application statistics and pending items."""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    status_counts = {}
    for row in conn.execute("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"):
        status_counts[row["status"]] = row["cnt"]

    pending = conn.execute(
        "SELECT id, company, position, status, date_applied FROM applications WHERE status NOT IN ('offer', 'rejected') ORDER BY updated_at DESC LIMIT 20"
    ).fetchall()
    conn.close()

    return json.dumps({
        "total_applications": total,
        "by_status": status_counts,
        "pending": [dict(r) for r in pending],
    })
'''


async def main():
    from types import SimpleNamespace
    config = SimpleNamespace(data_dir="./data")
    from opensable.core.skill_creator import SkillCreator
    creator = SkillCreator(config)

    print("Creating job_tracker skill...")
    result = await creator.create_skill(
        "job_tracker",
        "Job application tracker with SQLite — add, search, update status, summarize",
        JOB_TRACKER_CODE,
        metadata={"author": "sable", "version": "1.0"},
    )

    if result["success"]:
        print(f"  Skill created: {result['skill']}")
        print(f"  Path: {result['path']}")
        tool_info = result["tool_info"]
        print(f"  Tools: {tool_info['handler_names']}")
        print(f"  Schemas: {len(tool_info['schemas'])}")
        print(f"  Has initialize: {tool_info['has_initialize']}")

        # Run initialize to create DB
        module = result["module"]
        await module.initialize()
        print("  DB initialized")

        # Quick functional test
        from opensable.core.skill_creator import make_dynamic_handler
        add_handler = make_dynamic_handler(tool_info["handlers"]["job_add"])
        r = await add_handler({"company": "Google", "position": "Senior Software Engineer", "url": "https://careers.google.com/123", "status": "applied"})
        print(f"  Test add: {r}")

        search_handler = make_dynamic_handler(tool_info["handlers"]["job_search"])
        s = await search_handler({"query": "Google"})
        print(f"  Test search: {s}")

        summary_handler = make_dynamic_handler(tool_info["handlers"]["job_summary"])
        sm = await summary_handler({})
        print(f"  Test summary: {sm}")

        print("\n  Skill is registered and will auto-load on next backend restart.")
        print("  Restart the backend to make job_add, job_search, job_update_status, job_summary available in the agent.")
    else:
        print(f"  FAILED: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
