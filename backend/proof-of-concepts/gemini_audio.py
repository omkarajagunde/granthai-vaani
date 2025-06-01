# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
## Setup

To install the dependencies for this script, run:

```
brew install portaudio
pip install -U google-genai pyaudio
```

## API key

Ensure the `GOOGLE_API_KEY` environment variable is set to the api-key
you obtained from Google AI Studio.

## Run

To run the script:

```
python Get_started_LiveAPI_NativeAudio.py
```

Start talking to Gemini
"""

import asyncio
import base64
import json
import sys
import traceback

import pyaudio

from google import genai
from google.genai import types
from tools import get_tool
from prompts import get_prompt, get_tool_config
import websockets

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup  # noqa: E401

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1

# MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
# MODEL = "gemini-2.0-flash-exp"
MODEL = "gemini-2.0-flash-live-001"
API_KEY = "YOUR KEY HERE"
ASSISTANT_NAME = "yoda_diagnostics"
SYSTEM_PROMPT = get_prompt(ASSISTANT_NAME)
TOOL_CONFIG = get_tool_config(ASSISTANT_NAME)

pya = pyaudio.PyAudio()


client = genai.Client(
    api_key=API_KEY,
    http_options={"api_version": "v1beta"},
)

my_loop = asyncio.new_event_loop()
CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    # speech_config=types.SpeechConfig(
    #     voice_config=types.VoiceConfig(
    #         prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Sulafat")
    #     )
    # ),
    # context_window_compression=types.ContextWindowCompressionConfig(
    #     trigger_tokens=25600,
    #     sliding_window=types.SlidingWindow(target_tokens=12800),
    # ),
    realtime_input_config=types.RealtimeInputConfig(
        turn_coverage="TURN_INCLUDES_ALL_INPUT"
    ),
    system_instruction=SYSTEM_PROMPT,
    tools=[TOOL_CONFIG],
)


class AudioLoop:
    def __init__(self, websocket):
        self.websocket = websocket
        self.turn_complete = False
        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.audio_stream = None

        self.receive_audio_task = None
        self.play_audio_task = None

    async def handle_tool_call(self, tool_call):
        function_responses = []
        for fc in tool_call.function_calls:
            print("TOOL Used: ", fc.name)
            func_generator = get_tool(ASSISTANT_NAME, fc.name)
            resp = func_generator(**fc.args)
            function_response = types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={"result": resp},
                will_continue=False,
            )
            function_responses.append(function_response)
        await self.session.send_tool_response(function_responses=function_responses)

    async def listen_audio_from_websocket(self):
        # mic_info = pya.get_default_input_device_info()
        # self.audio_stream = await asyncio.to_thread(
        #     pya.open,
        #     format=FORMAT,
        #     channels=CHANNELS,
        #     rate=SEND_SAMPLE_RATE,
        #     input=True,
        #     input_device_index=mic_info["index"],
        #     frames_per_buffer=CHUNK_SIZE,
        # )
        # if __debug__:
        #     kwargs = {"exception_on_overflow": False}
        # else:
        #     kwargs = {}
        # while True:
        #     data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
        #     await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    if "realtime_input" in data:
                        for chunk in data["realtime_input"]["media_chunks"]:
                            if chunk["mime_type"] == "audio/pcm":
                                await self.out_queue.put(
                                    {"data": chunk["data"], "mime_type": "audio/pcm"}
                                )

                except Exception as e:
                    print(f"Error sending to Gemini: {e}")
            print("Client connection closed (send)")
        except Exception as e:
            print(f"Error sending to Gemini: {e}")
        finally:
            print("send_to_gemini closed")

    async def send_realtime_audio_to_gemini(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def receive_audio_from_gemini(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()

            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

                if tool_call := response.tool_call:
                    await self.handle_tool_call(tool_call)

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def send_audio_to_client(self):
        # stream = await asyncio.to_thread(
        #     pya.open,
        #     format=FORMAT,
        #     channels=CHANNELS,
        #     rate=24000,
        #     output=True,
        # )
        while True:
            print("send_audio_to_client/audio_in_queue - ", self.audio_in_queue)
            bytestream = await self.audio_in_queue.get()
            base64_audio = base64.b64encode(bytestream).decode("utf-8")
            await self.websocket.send(
                json.dumps(
                    {
                        "audio": base64_audio,
                    }
                )
            )

            # bytestream = await self.audio_in_queue.get()
            # await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        print("Please start speaking... start by saying hello...!")
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_realtime_audio_to_gemini())
                tg.create_task(self.listen_audio_from_websocket())
                tg.create_task(self.receive_audio_from_gemini())
                tg.create_task(self.send_audio_to_client())
        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:  # noqa: F821
            if self.audio_stream:
                self.audio_stream.close()
            traceback.print_exception(EG)


# if __name__ == "__main__":
#     loop = AudioLoop()
#     asyncio.run(loop.run())


async def gemini_session_handler(websocket):
    loop = AudioLoop(websocket)
    await loop.run()


async def main() -> None:
    async with websockets.serve(gemini_session_handler, "localhost", 9082):
        print("Running websocket server localhost:9082...")
        await asyncio.Future()  # Keep the server running indefinitely


if __name__ == "__main__":
    asyncio.run(main())
