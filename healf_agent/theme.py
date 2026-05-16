"""Editorial Wellness theme for the Streamlit chat surface.

Inject once at the top of chat_page() via theme.inject(st).
"""
from __future__ import annotations

FONT_LINKS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Manrope:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
"""

THEME_CSS = """
<style>
/* ── Design tokens ──────────────────────────────────────────── */
:root {
  --paper:         #F7F4EE;
  --paper-deep:    #EDE7D9;
  --paper-card:    #FFFFFF;
  --paper-line:    #D9D2C0;
  --ink:           #1A1F1A;
  --ink-soft:      #4A4F47;
  --ink-mute:      #8A8478;
  --moss:          #5B6F4A;
  --moss-deep:     #3E4F31;
  --moss-tint:     #E8EBDF;
  --terracotta:    #D4593C;
  --terracotta-d:  #B04528;

  --font-display:  'Fraunces', 'Cormorant Garamond', Georgia, serif;
  --font-body:     'Manrope', ui-sans-serif, system-ui, sans-serif;
  --font-mono:     'Geist Mono', 'JetBrains Mono', ui-monospace;

  --r-sm: 4px;
  --r-md: 10px;
  --r-lg: 16px;
  --hairline: 1px solid var(--paper-line);
}

/* ── Hide Streamlit chrome ──────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stDeployButton"],
#MainMenu,
footer { display: none !important; }

/* ── App canvas — paper background + grain ──────────────────── */
[data-testid="stAppViewContainer"] {
  background-color: var(--paper) !important;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.1 0 0 0 0 0.12 0 0 0 0 0.08 0 0 0 0.035 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>") !important;
}
[data-testid="stMain"] {
  font-family: var(--font-body) !important;
  color: var(--ink) !important;
  background: transparent !important;
}
[data-testid="stMainBlockContainer"] {
  background: transparent !important;
  padding-top: 2rem !important;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  background: transparent !important;
}

/* ── Sidebar ────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background-color: var(--paper-deep) !important;
  border-right: var(--hairline) !important;
  min-width: 280px !important;
  max-width: 280px !important;
}
[data-testid="stSidebarContent"] {
  background: transparent !important;
  padding: 0 !important;
}

/* ── Streamlit st.navigation() nav links (Chat / HITL Review) ── */
[data-testid="stSidebarNavItems"] {
  list-style: none !important;
  padding: 8px 8px 4px !important;
  margin: 0 !important;
  border-bottom: 1px solid var(--paper-line) !important;
}
[data-testid="stSidebarNavLink"] {
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
  padding: 9px 14px !important;
  font-family: var(--font-body) !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  color: #2A2F2A !important;
  text-decoration: none !important;
  border-radius: var(--r-md) !important;
  background: var(--paper-card) !important;
  border: 1px solid var(--paper-line) !important;
  margin: 2px 0 !important;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease !important;
}
[data-testid="stSidebarNavLink"]:hover {
  background: var(--moss-tint) !important;
  color: var(--moss-deep) !important;
  border-color: var(--moss) !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNavLink"][aria-selected="true"] {
  background: var(--moss) !important;
  color: #FFFFFF !important;
  border-color: var(--moss-deep) !important;
  font-weight: 700 !important;
}

/* Sidebar session-list buttons — flat list-row (only non-primary/secondary) */
[data-testid="stSidebar"] [data-testid="stButton"] > button:not([data-testid="stBaseButton-primary"]):not([data-testid="stBaseButton-secondary"]) {
  all: unset !important;
  display: block !important;
  box-sizing: border-box !important;
  width: 100% !important;
  font-family: var(--font-body) !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  color: var(--ink-soft) !important;
  padding: 10px 16px !important;
  border-left: 3px solid transparent !important;
  cursor: pointer !important;
  transition: background 100ms ease, color 100ms ease !important;
  text-align: left !important;
  white-space: pre-line !important;
  line-height: 1.35 !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:not([data-testid="stBaseButton-primary"]):not([data-testid="stBaseButton-secondary"]):hover {
  background: var(--moss-tint) !important;
  color: var(--ink) !important;
}

/* Active session — terracotta left bar */
[data-testid="stSidebar"] .session-active [data-testid="stButton"] > button {
  border-left-color: var(--terracotta) !important;
  color: var(--ink) !important;
  font-weight: 600 !important;
  background: rgba(212, 89, 60, 0.05) !important;
}

/* Sidebar all buttons — consistent font */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
  font-family: var(--font-body) !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  width: 100% !important;
}

/* Sidebar secondary buttons (New conversation) — outlined style */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
[data-testid="stSidebar"] button[kind="secondary"] {
  font-family: var(--font-body) !important;
  font-size: 13px !important;
  font-weight: 600 !important;
}

/* Sidebar primary buttons (Fetch product) — moss fill via config.toml primaryColor */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] button[kind="primary"] {
  font-family: var(--font-body) !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  letter-spacing: 0.02em !important;
}

/* Sidebar text input */
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
  font-family: var(--font-body) !important;
  font-size: 13px !important;
  background: var(--paper-card) !important;
  border: var(--hairline) !important;
  border-radius: var(--r-md) !important;
  color: var(--ink) !important;
  color-scheme: light !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input:focus {
  border-color: var(--moss) !important;
  box-shadow: 0 0 0 2px var(--moss-tint) !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] label {
  font-family: var(--font-body) !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.12em !important;
  color: var(--ink-mute) !important;
}

/* ── Chat messages ──────────────────────────────────────────── */
[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  padding: 4px 0 !important;
}

/* User bubble — moss green, right side */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"][aria-label*="user" i] [data-testid="stChatMessageContent"] {
  background: var(--moss) !important;
  color: var(--paper) !important;
  border-radius: 16px 16px 4px 16px !important;
  padding: 14px 18px !important;
  margin-left: auto !important;
  max-width: 75% !important;
  font-family: var(--font-body) !important;
  font-size: 15px !important;
  line-height: 1.6 !important;
}

/* Assistant bubble — white card, left side */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"][aria-label*="assistant" i] [data-testid="stChatMessageContent"] {
  background: var(--paper-card) !important;
  border: var(--hairline) !important;
  border-radius: 16px 16px 16px 4px !important;
  padding: 18px 22px !important;
  max-width: 85% !important;
  font-family: var(--font-body) !important;
  font-size: 15px !important;
  line-height: 1.65 !important;
  color: var(--ink) !important;
}

/* Avatar icons — suppress defaults, keep minimal */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
  background: transparent !important;
  border: none !important;
  color: var(--ink-mute) !important;
  font-size: 14px !important;
}

/* ── Debug expanders — quieter visual weight ────────────────── */
[data-testid="stExpander"] {
  border: var(--hairline) !important;
  border-radius: var(--r-md) !important;
  background: transparent !important;
  margin-top: 6px !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--font-body) !important;
  font-size: 12px !important;
  color: var(--ink-mute) !important;
  letter-spacing: 0.04em !important;
  padding: 8px 12px !important;
}
[data-testid="stExpander"] summary:hover {
  color: var(--ink-soft) !important;
  background: var(--moss-tint) !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  background: var(--paper-card) !important;
  border-top: var(--hairline) !important;
  padding: 12px !important;
}

/* ── Chat input — forced light, defeats OS dark mode ────────── */
[data-testid="stBottomBlockContainer"] {
  background-color: var(--paper) !important;
  background-image: none !important;
  border-top: 1px solid var(--paper-line) !important;
  padding: 12px 20px 16px !important;
  color-scheme: light !important;
}
[data-testid="stChatInput"],
[data-testid="stChatInputContainer"] {
  background-color: var(--paper-card) !important;
  border: 1px solid var(--paper-line) !important;
  border-radius: 12px !important;
  font-family: var(--font-body) !important;
  color-scheme: light !important;
}
[data-testid="stChatInput"]:focus-within,
[data-testid="stChatInputContainer"]:focus-within {
  border-color: var(--moss) !important;
  box-shadow: 0 0 0 3px var(--moss-tint) !important;
}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInputTextArea"] {
  background-color: var(--paper-card) !important;
  color: var(--ink) !important;
  -webkit-text-fill-color: var(--ink) !important;
  caret-color: var(--moss) !important;
  font-family: var(--font-body) !important;
  font-size: 15px !important;
  color-scheme: light !important;
}
[data-testid="stChatInput"] textarea::placeholder,
[data-testid="stChatInputTextArea"]::placeholder {
  color: var(--ink-mute) !important;
  -webkit-text-fill-color: var(--ink-mute) !important;
  opacity: 1 !important;
}
[data-testid="stChatInput"] button {
  background: var(--moss) !important;
  color: var(--paper) !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
}
[data-testid="stChatInput"] button:hover {
  background: var(--moss-deep) !important;
}

/* ── Welcome chip buttons (in main pane columns) ────────────── */
.chip-btn .stButton > button {
  background: var(--paper-card) !important;
  border: var(--hairline) !important;
  border-radius: var(--r-lg) !important;
  font-family: var(--font-body) !important;
  font-size: 13px !important;
  color: var(--ink-soft) !important;
  text-align: left !important;
  padding: 14px 16px !important;
  width: 100% !important;
  height: 72px !important;
  cursor: pointer !important;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease !important;
  box-shadow: none !important;
  white-space: normal !important;
  line-height: 1.4 !important;
}
.chip-btn .stButton > button:hover {
  background: var(--moss-tint) !important;
  border-color: var(--moss) !important;
  color: var(--ink) !important;
}

/* ── Success / info alerts ──────────────────────────────────── */
[data-testid="stAlert"] {
  background: var(--moss-tint) !important;
  border-color: var(--moss) !important;
  color: var(--ink) !important;
  border-radius: var(--r-md) !important;
  font-family: var(--font-body) !important;
  font-size: 14px !important;
}

/* ── Spinner ────────────────────────────────────────────────── */
[data-testid="stSpinner"] {
  color: var(--moss) !important;
}

/* ── Dataframe (debug timing table) ────────────────────────── */
[data-testid="stDataFrame"] {
  font-family: var(--font-mono) !important;
  font-size: 12px !important;
}

/* ── Markdown tables — editorial hairline grid ──────────────── */
[data-testid="stMarkdownContainer"] table {
  border-collapse: collapse !important;
  width: 100% !important;
  font-family: var(--font-body) !important;
  font-size: 14px !important;
  margin: 12px 0 !important;
  border: 1px solid var(--paper-line) !important;
  border-radius: var(--r-md) !important;
  overflow: hidden !important;
}
[data-testid="stMarkdownContainer"] th {
  background: var(--moss-tint) !important;
  color: var(--ink) !important;
  font-weight: 700 !important;
  font-size: 12px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  padding: 10px 14px !important;
  text-align: left !important;
  border: 1px solid var(--paper-line) !important;
  border-bottom: 2px solid var(--moss) !important;
}
[data-testid="stMarkdownContainer"] td {
  padding: 9px 14px !important;
  border: 1px solid var(--paper-line) !important;
  color: var(--ink) !important;
  vertical-align: top !important;
  line-height: 1.5 !important;
}
[data-testid="stMarkdownContainer"] tr:nth-child(even) td {
  background: var(--paper) !important;
}
[data-testid="stMarkdownContainer"] tr:nth-child(odd) td {
  background: var(--paper-card) !important;
}
[data-testid="stMarkdownContainer"] tr:hover td {
  background: var(--moss-tint) !important;
}
</style>
"""


def inject(st) -> None:
    """Inject fonts and CSS into the Streamlit page. Call once at the top of chat_page()."""
    st.markdown(FONT_LINKS, unsafe_allow_html=True)
    st.markdown(THEME_CSS, unsafe_allow_html=True)
