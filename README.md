# RELAY

RELAY is an interruptible, multilingual voice AI support system built around one key idea:

> Don’t transfer the call. Transfer the intelligence.

The system is designed for real-time support conversations where the customer can interrupt the AI mid-response, clarify the issue, and request a human agent without restarting the conversation.

The current implementation is a working hackathon-ready MVP focused on the core flow:

- real-time voice session
- live transcript
- interruption / barge-in state
- context preservation after interruption
- escalation detection
- structured human handoff
- human takeover flow

This project intentionally avoids payments, orders, banking, or external e-commerce logic because the overall product goal is the voice-agent architecture itself, not a business backend.

---

## Problem

When AI support fails, customers are often forced to repeat the entire issue to a human agent. Most voice bots also struggle with natural interruption and context updates.

## Solution

RELAY allows a customer to continue naturally in English, Hindi, or Hinglish, interrupt the AI while it is speaking, and preserve the context so the human agent receives the full support story without repetition.

---

## Architecture

- Frontend: browser-based interface for voice, transcript, and agent trace
- Backend: FastAPI app with session state handling, escalation logic, and handoff APIs
- Voice platform: AssemblyAI Voice Agent API
- Storage: in-memory session state and trace events for hackathon use
- Human handoff: structured JSON summary pushed to the interface for takeover

---

## Core workflow

1. User opens the voice app.
2. Web app requests a temporary token from the backend.
3. Browser connects to AssemblyAI Voice Agent API.
4. AI begins a support conversation.
5. User interrupts mid-response.
6. AI stops and updates the current context.
7. Agent continues from the updated conversation state.
8. User asks to speak to a human.
9. Escalation engine marks the session for handoff.
10. Human dashboard shows full context and takeover controls.

---

## Setup

### 1. Create environment

```bash
cp .env.example .env
```

Then add your real AssemblyAI API key:

```bash
ASSEMBLYAI_API_KEY=your_key_here
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the backend

```bash
python server.py
```

Then open:

```text
http://localhost:8000
```

---

## Environment variables

Required:

```bash
ASSEMBLYAI_API_KEY=...
```

Do not place the permanent key in frontend code.

---

## Files

- [server.py](server.py): FastAPI app and demo endpoints
- [static/index.html](static/index.html): voice interface and dashboard UI
- [backend/config.py](backend/config.py): config and environment constants
- [backend/agent/state.py](backend/agent/state.py): structured session state
- [backend/agent/controller.py](backend/agent/controller.py): interruption and escalation logic
- [backend/escalation/engine.py](backend/escalation/engine.py): deterministic escalation rules
- [backend/tools/support.py](backend/tools/support.py): generic support tools
- [.env.example](.env.example): example secret file

---

## Demo flow

The interface currently demonstrates this flow:

1. User starts the voice call.
2. AI greets the user.
3. Customer says they have an account problem.
4. User interrupts to clarify the issue.
5. Session updates from the new context.
6. User requests human support.
7. Handoff summary appears.
8. Human takeover is available.

---

## Known limitations

- This is an MVP and not a production call center platform.
- Human takeover is implemented as a structured UI flow, not a full multi-agent live call infrastructure.
- Audio flow is browser-based and depends on microphone permission and browser support.
- Hindi/Hinglish understanding depends on AssemblyAI’s actual capabilities and is not guaranteed for all speech patterns.
- The app uses in-memory session state for the demo, which is appropriate for a hackathon but not for production persistence.

---

## What to test

- Start voice session.
- Speak naturally.
- Interrupt while the AI is talking.
- Watch the UI switch to INTERRUPTED and then CONTEXT UPDATED.
- Trigger a human escalation.
- Confirm that the handoff summary includes the issue, context, and actions.
- Click takeover and verify the human status changes to HUMAN JOINED.

---

## Goal of the project

The project demonstrates the actual core innovation of RELAY:

VOICE AI
+
INTERRUPTION
+
CONTEXT UPDATE
+
ESCALATION
+
HUMAN HANDOFF
+
CONTEXT PRESERVED

That is the product.
