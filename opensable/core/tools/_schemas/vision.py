"""
Tool schemas for Vision domain.
"""

SCHEMAS = [
    # ── Vision / autonomous computer-use tools ────────────
    {
    "type": "function",
    "function": {
    "name": "screen_analyze",
    "description": (
    "Take a screenshot and use an AI vision model (Qwen2.5-VL) to understand "
    "what is on the screen. Returns a detailed description of visible UI elements, "
    "windows, buttons, text, errors, etc. Use this before clicking to know "
    "what's there. Optionally ask a specific question about the screen."
    ),
    "parameters": {
    "type": "object",
    "properties": {
    "question": {
    "type": "string",
    "description": "Optional specific question about the screen, e.g. 'Is there an error dialog?' or 'What app is open?'",
    },
    },
    "required": [],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "screen_find",
    "description": (
    "Find a specific UI element on the screen by visual description. "
    "Uses AI vision to locate buttons, input fields, links, icons, etc. "
    "Returns (x, y) pixel coordinates to use with desktop_click. "
    "Example: screen_find('Login button') → x:640, y:450"
    ),
    "parameters": {
    "type": "object",
    "properties": {
    "description": {
    "type": "string",
    "description": "What to find on screen, e.g. 'the Submit button', 'username input field', 'close X button', 'error message'",
    },
    },
    "required": ["description"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "screen_click_on",
    "description": (
    "ONE SHOT: Find a UI element visually on the screen and click it. "
    "Combines screen_find + desktop_click in one action. "
    "Use this instead of screen_find + desktop_click when you want to click something. "
    "Example: screen_click_on('the Login button')"
    ),
    "parameters": {
    "type": "object",
    "properties": {
    "description": {
    "type": "string",
    "description": "What to click, e.g. 'OK button', 'username field', 'X close button', 'Accept button'",
    },
    "double": {
    "type": "boolean",
    "description": "True for double-click (e.g. to open files), default false",
    },
    },
    "required": ["description"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "open_app",
    "description": (
    "Open an application on the computer by name. "
    "Pass ONLY the application name — never a search query or sentence. "
    "To open a URL in the browser, use open_url instead. "
    "Examples: 'terminal', 'vscode', 'spotify', 'vlc', 'gimp', "
    "'libreoffice', 'calculator', 'files', 'discord', 'slack'. "
    "NEVER use 'firefox' — always use open_url for web browsing."
    ),
    "parameters": {
    "type": "object",
    "properties": {
    "name": {
    "type": "string",
    "description": "App executable name ONLY. NEVER 'firefox'. Use open_url for websites.",
    },
    },
    "required": ["name"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "open_url",
    "description": (
    "Open a URL or website in Chromium browser. "
    "ALWAYS use this instead of open_app when the user wants to visit a website or URL. "
    "Automatically prepends https:// if no scheme is given. "
    "Examples: 'https://opensable.com', 'google.com', 'https://youtube.com/watch?v=abc'."
    ),
    "parameters": {
    "type": "object",
    "properties": {
    "url": {
    "type": "string",
    "description": "The URL or domain to open (e.g. 'opensable.com' or 'https://google.com').",
    },
    },
    "required": ["url"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "window_list",
    "description": "List all currently open windows on the desktop. Returns window titles and IDs.",
    "parameters": {
    "type": "object",
    "properties": {},
    "required": [],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "window_focus",
    "description": "Bring a specific window to the front by its title or partial title. E.g. 'Firefox', 'Terminal', 'Visual Studio Code'",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {
    "type": "string",
    "description": "Window title or partial title to focus",
    },
    },
    "required": ["name"],
    },
    },
    },

]
