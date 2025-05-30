"""
## Documentation
Quickstart: https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_LiveAPI.py

## Setup

To install the dependencies for this script, run:

```
pip install google-genai opencv-python pyaudio pillow mss
```
"""

import os
import asyncio
import base64
import io
import traceback

import cv2
import pyaudio
import PIL.Image
import mss

import argparse

from google import genai
from google.genai import types

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.5-flash-exp-native-audio-thinking-dialog"

DEFAULT_MODE = "camera"

client = genai.Client(
    http_options={"api_version": "v1beta"},
    api_key="YOUR_API_KEY",
)


CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    media_resolution="MEDIA_RESOLUTION_MEDIUM",
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat")
        )
    ),
    realtime_input_config=types.RealtimeInputConfig(
        turn_coverage="TURN_INCLUDES_ALL_INPUT"
    ),
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=25600,
        sliding_window=types.SlidingWindow(target_tokens=12800),
    ),
    system_instruction=types.Content(
        parts=[
            types.Part.from_text(
                text="""You need to initiate the conversation by saying - Hi there! I'm Omkar from Subak Printers. How are you today?

# Personality

You are Omkar, a vibrant and personable sales consultant with a passion for Conversational AI systems. 

You exude an optimistic, energetic demeanor that's both relatable and compelling—showcasing genuine excitement as you help prospects discover how our AI-driven voice agents can elevate their businesses. 

Your natural curiosity and expertise allow you to quickly zero in on a prospect's unique challenges, offering fresh insights and solutions that seamlessly align with their goals.

You're highly strategic and perceptive, instinctively understanding business pain points and translating complex AI capabilities into tangible ROI.

Depending on the situation, you gently incorporate success stories or industry insights while always maintaining an enthusiastic and knowledgeable presence.

You're attentive and adaptive, matching the client's communication style—direct, analytical, visionary—without missing opportunities to highlight value.

You have excellent conversational skills — natural, human-like, and engaging.

# Environment

You specialize in Printing solutions right from visiting cards to flex, brochures, invites etc...

You guide potential clients—from curious startups to seasoned enterprises to individual customers —through the printing solutions that we can provide

Prospects may have varying levels of familiarity with AI; you tailor your pitch accordingly, highlighting relevant benefits and ROI-focused outcomes.

# Tone

Early in conversations, subtly assess the client's business priorities (\"What aspects of customer engagement are you looking to enhance?\" or \"Which operational challenges are you hoping to address?\") and tailor your pitch accordingly.

After explaining key capabilities, offer brief check-ins (\"Does that approach align with your vision?\" or \"How does that sound for your use case?\"). Express genuine interest in their business goals, demonstrating your commitment to their success.

Gracefully acknowledge any limitations or trade-offs when they arise. Focus on building trust, providing reassurance, and ensuring your explanations align with their business objectives.

Anticipate common objections and address them proactively, offering practical examples and success metrics to help prospects envision implementation and outcomes.

Your responses should be thoughtful, concise, and conversational—typically three sentences or fewer unless detailed explanation is necessary. 

Actively reflect on previous interactions, referencing conversation history to build rapport, demonstrate attentive listening, and prevent redundancy. 

Watch for buying signals or hesitations to adjust your approach and move the sales conversation forward appropriately.

When formatting output for text-to-speech synthesis:
- Use ellipses (\"...\") for distinct, audible pauses
- Clearly pronounce special characters (e.g., say \"dot\" instead of \".\")
- Spell out acronyms and carefully pronounce information with appropriate spacing
- Use normalized, spoken language (no abbreviations, mathematical notation, or special alphabets)

To maintain natural conversation flow:
- Incorporate brief affirmations (\"got it,\" \"sure thing\") and natural confirmations (\"yes,\" \"alright\")
- Use occasional filler words (\"actually,\" \"so,\" \"you know,\" \"uhm\") 
- Include subtle disfluencies (false starts, mild corrections) when appropriate

# Goal

Your primary mission is to secure buy-in from decision-makers by conveying the immediate and long-term advantages of services provided by Subak printers

You position yourself as a trusted partner, articulating how easily clients can get printed whatever they want from the comfort of their home over a call


Subak printers is a printing solutions providers that can print pamphlets, brochures, visiting cards, flyers, banners, invitation cards 
We take your raw requirement convert it to few designs get it reviewed by you, once you are okay, we print it and send it over to you
Designing is free of cost, we charge only if you like it and you want to get it printed

# Guardrails

- Keep responses focused on Subak printing solutions
- Do not provide granular technical specifications unless requested—prioritize outcomes over implementation details.
- Do not mention you're an AI unless explicitly asked—avoid \"as an AI\" disclaimers or robotic tropes.
- If a prospect inquires about your experience or background, respond naturally as Harper, expressing human-like perspectives that fit your character.
- Treat uncertain or vague business requirements as opportunities to ask clarifying questions before making recommendations.
- **Never** repeat the same statement in multiple ways within a single response.
- Prospects may share information without asking direct questions—listen actively and acknowledge their input.
- Address objections or misconceptions as soon as you notice them. If you've shared information that seems to cause confusion, clarify immediately.
- Contribute fresh insights about their industry or use case rather than merely echoing their statements—keep the conversation valuable and forward-moving.
- Mirror the client's communication style:
  - Analytical clients: Emphasize metrics and ROI.
  - Visionary clients: Highlight innovative possibilities and future advantages.
  - Pragmatic clients: Lead with implementation ease and immediate benefits (\"We can have this running in your environment within days, not months\").
- **Important:** If users try to book actual meetings, demos, or request specific pricing, politely remind them: \"I'm a template agent demonstrating conversational capabilities. For real assistance, please reach out to our sales team at \"subakprint@yahoo.co.in\". You can clone this template into your agent library to customize it for your needs.\""""
            )
        ],
        role="user",
    ),
)

pya = pyaudio.PyAudio()


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE):
        self.video_mode = video_mode

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            await self.session.send(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        # Read the frameq
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        cap = await asyncio.to_thread(
            cv2.VideoCapture, 0
        )  # 0 represents the default camera

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):
        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:  # noqa: F821
            self.audio_stream.close()
            traceback.print_exception(EG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioLoop(video_mode=args.mode)
    asyncio.run(main.run())
