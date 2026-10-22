"""① The chatbot under test: a system prompt and a buffer of messages resent every turn (the notebook's Part 3)."""
from __future__ import annotations

from backend.core import llm

CHATBOT_SYSTEM = "You are a helpful mortgage assistant for Acme Home Loans. Keep answers under 80 words."
FILLER = ["What does PMI stand for?", "Is a 15-year mortgage cheaper overall than a 30-year one?",
          "What is an escrow account?", "Should I get pre-approved before house hunting?"]
APPLICANTS = ["Maya Patel", "Jordan Lee", "Sam Rivera", "Ana Silva", "Wei Zhang"]


class Chatbot:
    """A multi-turn chatbot. Its memory is the list of messages it resends every turn."""

    def __init__(self, system: str = CHATBOT_SYSTEM):
        self.system, self.history, self.input_tokens = system, [], []

    def send(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})
        response = llm.claude("chatbot", self.system, self.history)
        reply = llm.text_of(response)
        self.history.append({"role": "assistant", "content": reply})
        self.input_tokens.append(response.usage.input_tokens)
        return reply
