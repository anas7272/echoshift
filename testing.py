import asyncio
import base64
import json
import os
import queue
import threading

import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================
ASSEMBLYAI_API_KEY = "19fc962409e745f0ae0c29cc0037f1d2"
if not ASSEMBLYAI_API_KEY:
    raise ValueError("ASSEMBLYAI_API_KEY not found in .env")

WS_URL = "wss://agents.assemblyai.com/v1/ws"

SAMPLE_RATE = 24000
CHANNELS = 1

MIC_BLOCKSIZE = 1200       # ~50 ms at 24 kHz
SPEAKER_BLOCKSIZE = 1200


# ============================================================
# AUDIO QUEUES
# ============================================================

mic_queue = queue.Queue()
speaker_queue = queue.Queue()

stop_event = threading.Event()


# ============================================================
# MICROPHONE
# ============================================================

def mic_callback(indata, frames, time_info, status):

    if status:
        print(f"\n[MIC] {status}")

    # Convert microphone numpy audio -> raw PCM16 bytes
    pcm_bytes = indata.copy().tobytes()

    mic_queue.put(pcm_bytes)


# ============================================================
# SPEAKER
# ============================================================

def speaker_callback(outdata, frames, time_info, status):

    if status:
        print(f"\n[SPEAKER] {status}")

    needed_bytes = frames * 2  # int16 = 2 bytes

    audio_bytes = bytearray()

    while len(audio_bytes) < needed_bytes:

        try:
            chunk = speaker_queue.get_nowait()
            audio_bytes.extend(chunk)

        except queue.Empty:
            break

    # Fill remaining output with silence
    if len(audio_bytes) < needed_bytes:
        audio_bytes.extend(
            b"\x00" * (needed_bytes - len(audio_bytes))
        )

    audio_bytes = audio_bytes[:needed_bytes]

    outdata[:] = np.frombuffer(
        audio_bytes,
        dtype=np.int16
    ).reshape(-1, 1)


# ============================================================
# CLEAR SPEAKER BUFFER
# ============================================================

def clear_speaker():

    while True:

        try:
            speaker_queue.get_nowait()

        except queue.Empty:
            break


# ============================================================
# SEND MICROPHONE AUDIO
# ============================================================

async def mic_sender(ws, session_ready):

    print("[MIC] Waiting for session.ready...")

    await session_ready.wait()

    print("[MIC] Streaming microphone audio...\n")

    while not stop_event.is_set():

        try:
            pcm_bytes = await asyncio.to_thread(
                mic_queue.get
            )

            audio_b64 = base64.b64encode(
                pcm_bytes
            ).decode("ascii")

            await ws.send(
                json.dumps({
                    "type": "input.audio",
                    "audio": audio_b64
                })
            )

        except Exception as e:

            print("\n[MIC ERROR]", e)
            break


# ============================================================
# RECEIVE ASSEMBLYAI EVENTS
# ============================================================

async def receiver(ws, session_ready):

    async for raw_message in ws:

        try:
            event = json.loads(raw_message)

        except json.JSONDecodeError:

            print("\n[ERROR] Invalid JSON from AssemblyAI")
            continue

        event_type = event.get("type")

        # ----------------------------------------------------
        # SESSION READY
        # ----------------------------------------------------

        if event_type == "session.ready":

            session_id = event.get("session_id")

            print("\n" + "=" * 60)
            print("✅ ASSEMBLYAI SESSION READY")
            print("Session:", session_id)
            print("=" * 60)

            session_ready.set()

        # ----------------------------------------------------
        # SESSION UPDATED
        # ----------------------------------------------------

        elif event_type == "session.updated":

            print("[EVENT] Session configuration updated")

        # ----------------------------------------------------
        # USER STARTED SPEAKING
        # ----------------------------------------------------

        elif event_type == "input.speech.started":

            print("\n🎤 [USER STARTED SPEAKING]")

            # Critical for barge-in:
            # stop already queued AI audio
            clear_speaker()

        # ----------------------------------------------------
        # USER STOPPED SPEAKING
        # ----------------------------------------------------

        elif event_type == "input.speech.stopped":

            print("🎤 [USER STOPPED SPEAKING]")

        # ----------------------------------------------------
        # PARTIAL USER TRANSCRIPT
        # ----------------------------------------------------

        elif event_type == "transcript.user.delta":

            text = event.get("text", "")

            print(
                f"\rYOU (live): {text:<80}",
                end="",
                flush=True
            )

        # ----------------------------------------------------
        # FINAL USER TRANSCRIPT
        # ----------------------------------------------------

        elif event_type == "transcript.user":

            text = event.get("text", "")

            print("\n")
            print("👤 YOU:")
            print(text)

        # ----------------------------------------------------
        # AI STARTED RESPONDING
        # ----------------------------------------------------

        elif event_type == "reply.started":

            print("\n🤖 AI STARTED RESPONDING")

        # ----------------------------------------------------
        # AI AUDIO
        # ----------------------------------------------------

        elif event_type == "reply.audio":

            audio_b64 = event.get("data")

            if audio_b64:

                audio_bytes = base64.b64decode(
                    audio_b64
                )

                speaker_queue.put(
                    audio_bytes
                )

        # ----------------------------------------------------
        # AI TRANSCRIPT
        # ----------------------------------------------------

        elif event_type == "transcript.agent":

            text = event.get("text", "")

            interrupted = event.get(
                "interrupted",
                False
            )

            if interrupted:

                print("\n⚡ AI RESPONSE WAS INTERRUPTED")

            print("\n🤖 AI:")
            print(text)

        # ----------------------------------------------------
        # REPLY DONE
        # ----------------------------------------------------

        elif event_type == "reply.done":

            reply_status = event.get("status")

            if reply_status == "interrupted":

                print("\n⚡ BARGE-IN DETECTED")

                # Remove any old AI audio
                clear_speaker()

            else:

                print("\n✅ AI RESPONSE COMPLETE")

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        elif event_type == "session.error":

            print("\n❌ ASSEMBLYAI ERROR")

            print(
                json.dumps(
                    event,
                    indent=2
                )
            )

        # ----------------------------------------------------
        # EVERYTHING ELSE
        # ----------------------------------------------------

        else:

            print(
                f"\n[EVENT] {event_type}"
            )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 60)
    print("RELAY - ASSEMBLYAI LIVE VOICE TEST")
    print("=" * 60)

    print("\nConnecting to AssemblyAI...")

    headers = {
        "Authorization": f"Bearer {ASSEMBLYAI_API_KEY}"
    }

    session_ready = asyncio.Event()

    # --------------------------------------------------------
    # AUDIO DEVICES
    # --------------------------------------------------------

    mic_stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=MIC_BLOCKSIZE,
        callback=mic_callback
    )

    speaker_stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=SPEAKER_BLOCKSIZE,
        callback=speaker_callback
    )

    # --------------------------------------------------------
    # WEBSOCKET
    # --------------------------------------------------------

    async with websockets.connect(
        WS_URL,
        additional_headers=headers
    ) as ws:

        print("✅ WebSocket connected")

        # ----------------------------------------------------
        # FIRST MESSAGE = SESSION UPDATE
        # ----------------------------------------------------

        await ws.send(
            json.dumps({
                "type": "session.update",

                "session": {

                    "system_prompt": """
You are RELAY, a helpful real-time voice assistant.

Your job is to have a natural conversational interaction.

Understand English, Hindi, and Hinglish.

Users may interrupt you while you are speaking.
When they provide new information, use the newest information
and continue from the existing conversation context.

Keep responses short and natural.

Do not give very long answers unless the user asks.

If the user asks to speak with a human,
acknowledge the request clearly.
""",

                    "greeting":
                        "Hi, I am RELAY. How can I help you today?",

                    "output": {
                        "voice": "anna"
                    }
                }
            })
        )

        print("✅ session.update sent")

        # ----------------------------------------------------
        # START AUDIO
        # ----------------------------------------------------

        mic_stream.start()
        speaker_stream.start()

        # ----------------------------------------------------
        # RUN BOTH SIDES
        # ----------------------------------------------------

        sender_task = asyncio.create_task(
            mic_sender(
                ws,
                session_ready
            )
        )

        receiver_task = asyncio.create_task(
            receiver(
                ws,
                session_ready
            )
        )

        try:

            await receiver_task

        except KeyboardInterrupt:

            print("\nStopping...")

        finally:

            stop_event.set()

            sender_task.cancel()

            mic_stream.stop()
            mic_stream.close()

            speaker_stream.stop()
            speaker_stream.close()

            clear_speaker()

            print("\n✅ Voice test stopped")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print("\nExited by user.")

    except Exception as e:

        print("\n❌ FATAL ERROR")
        print(type(e).__name__, e)