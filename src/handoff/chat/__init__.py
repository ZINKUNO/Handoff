# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Chat with a workspace: a Strands agent whose thread survives restarts."""

from handoff.chat.service import ChatService, get_chat_service

__all__ = ["ChatService", "get_chat_service"]
