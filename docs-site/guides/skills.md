# Skills & Capabilities

Open-Sable ships with **22 built-in skills** organised into four categories.
Every skill is a Python class that the agent can invoke autonomously via tool calls.

```
opensable/skills/
├── social/        # 7 skills — social-media platforms
├── media/         # 3 skills — image, voice, OCR
├── data/          # 5 skills — databases, documents, files
├── automation/    # 6 skills — code, API, browser, email
├── trading/       # multi-exchange trading engine
└── community/     # 16 community-contributed skills
```

---

## Social (7 skills)

Interact with major social platforms.  All social skills require the platform's own library and credentials.

| Skill | Description | Library |
|-------|-------------|---------|
| **XSkill** | Post, search, reply on X (Twitter) | `twikit` |
| **GrokSkill** | Free Grok AI via X account | `twikit_grok` |
| **InstagramSkill** | Post, search, interact on Instagram | `instagrapi` |
| **FacebookSkill** | Graph-API posts, pages, interactions | `facebook-sdk` |
| **LinkedInSkill** | Search people, post updates, DMs | `linkedin-api` |
| **TikTokSkill** | Browse trending, search users/videos | `TikTokApi` |
| **YouTubeSkill** | Search, browse, upload videos | `python-youtube` |

!!! warning "Social credentials"
    All social skills are provided for **educational and testing purposes only**.
    Add credentials in `.env` — never hard-code tokens in source files.

### Example — Post to X

```python
from opensable.skills.social.x_skill import XSkillImpl

x = XSkillImpl()
await x.post_tweet("Hello from Open-Sable! 🤖")
```

---

## Media (3 skills)

Generate images, perform OCR, and handle voice I/O.

| Skill | Description | Library |
|-------|-------------|---------|
| **ImageSkill** | Image generation & analysis (Pillow, DALL-E) | `Pillow` |
| **VoiceSkill** | Text-to-Speech + Speech-to-Text | `whisper`, `piper-tts` |
| **OCRSkill** | Extract text from images & scanned PDFs | `pytesseract` |

### Example — Generate an image

```python
from opensable.skills.media.image_skill import ImageSkillImpl

img = ImageSkillImpl()
result = await img.generate_image("a sunset over the ocean")
print(result["path"])   # /path/to/generated/image.png
```

---

## Data (5 skills)

Store, query, and manage structured data and documents.

| Skill | Description | Library |
|-------|-------------|---------|
| **DatabaseSkill** | Query SQL & NoSQL databases | `sqlalchemy`, `motor` |
| **RAGSkill** | Retrieval-augmented generation pipeline | `chromadb` |
| **FileManager** | Upload, download, organise files | built-in |
| **DocumentSkill** | Create Word, Excel, PDF, PowerPoint files | `python-docx`, `openpyxl`, `reportlab` |
| **ClipboardSkill** | Cross-platform copy / paste / clear | `pyperclip` |

### Example — Create a Word document

```python
from opensable.skills.data.document_skill import DocumentSkillImpl

doc = DocumentSkillImpl()
result = await doc.create_document(
    doc_type="word",
    title="Weekly Report",
    content="This week we shipped v1.1.0 ..."
)
print(result["path"])   # /path/to/Weekly_Report.docx
```

---

## Automation (6 skills)

Execute code, call APIs, browse the web, send emails, and manage calendars.

| Skill | Description | Library |
|-------|-------------|---------|
| **CodeExecutor** | Sandboxed code execution (Python, JS, Bash, …) | built-in |
| **APIClient** | Call external REST APIs with retries & auth | `httpx` |
| **BrowserSkill** | Full browser automation | `playwright` |
| **AdvancedScraper** | Intelligent web scraping (Maxun-style) | `playwright`, `beautifulsoup4` |
| **EmailSkill** | Send & read email (SMTP/IMAP) | `smtplib`, `imaplib` |
| **CalendarSkill** | Local JSON-based calendar (no Google dependency) | built-in |

### Example — Run Python code safely

```python
from opensable.skills.automation.code_executor import CodeExecutorImpl

executor = CodeExecutorImpl()
result = await executor.execute_code("print(2 + 2)", language="python")
print(result["output"])   # "4"
```

---

## Trading

See the dedicated [Trading Guide](trading.md) for full details on the multi-exchange
trading engine, which supports paper trading, crypto, stocks, and prediction markets.

---

## Community Skills

16 community-contributed skills are available in `opensable/skills/community/`.
Browse the catalog in `skills_catalog.json` or install them via the SkillFactory:

```python
# In a conversation with Sable:
#   "Install the weather skill"
#   "Show me available community skills"
```

See `opensable/skills/community/SKILL.md` for the skill authoring spec.

---

## Creating Your Own Skill

Use the built-in `SkillFactory` to generate a skill from a natural language description:

```
You: "Create a skill that checks GitHub pull requests"
Sable: ✅ Created skill 'github_pr_checker' in opensable/skills/created/
```

Or manually:

1. Create a file in `opensable/skills/created/my_skill.py`
2. Define a class with `async def execute(self, **params)` methods
3. The agent will auto-discover it on next restart

See [Self-Modification Guide](self-modification.md) for details on runtime skill creation.
