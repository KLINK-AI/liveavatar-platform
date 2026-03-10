"""
Shared ConversationEngine singleton.

CRITICAL: Both sessions.py and conversations.py must use the SAME engine
instance so that WebSocket managers registered during session creation
are available when processing conversation messages.

Without this, the WS manager registered in sessions.py's engine
would not be found by conversations.py's engine, causing
"No WebSocket connection for session" errors and breaking
the TTS → WebSocket → Avatar lip-sync pipeline.
"""

from typing import Optional
from services.conversation.engine import ConversationEngine

_engine: Optional[ConversationEngine] = None


def get_engine() -> ConversationEngine:
    """
    Get the shared ConversationEngine singleton.

    This must be the ONLY way to get an engine instance
    in the entire application.
    """
    global _engine
    if _engine is None:
        _engine = ConversationEngine()
    return _engine
