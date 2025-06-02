import asyncio
import base64
import json
import os
import traceback
from google import genai
from google.genai import types
from tools import get_tool
import http
import signal
from prompts import get_prompt, get_tool_config
import websockets
import pyaudio

pya = pyaudio.PyAudio()

# MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
# MODEL = "gemini-2.0-flash-exp"
MODEL = "gemini-2.0-flash-live-001"
API_KEY = os.getenv("GOOGLE_API_KEY")
ASSISTANT_NAME = "yoda_diagnostics"
SYSTEM_PROMPT = get_prompt(ASSISTANT_NAME)
TOOL_CONFIG = get_tool_config(ASSISTANT_NAME)

client = genai.Client(
    api_key=API_KEY,
    http_options={"api_version": "v1alpha"},
)

my_loop = asyncio.new_event_loop()
CONFIG = types.LiveConnectConfig(
    response_modalities=[
        "AUDIO",
    ],
    # enable_affective_dialog=True, // only available for gemini-2.5-flash-preview-native-audio-dialog
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
    # context_window_compression=types.ContextWindowCompressionConfig(
    #     trigger_tokens=25600,
    #     sliding_window=types.SlidingWindow(target_tokens=12800),
    # ),
    # realtime_input_config=types.RealtimeInputConfig(
    #     turn_coverage="TURN_INCLUDES_ALL_INPUT"
    # ),
    system_instruction=SYSTEM_PROMPT,
    tools=[TOOL_CONFIG],
)


class AudioLoop:
    def __init__(self, websocket):
        self.websocket = websocket
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None

    async def handle_tool_call(self, tool_call):
        function_responses = []
        for fc in tool_call.function_calls:
            print("TOOL Used - ", fc.name)
            await self.websocket.send(
                json.dumps(
                    {
                        "assistant_activity": f"TOOL called - {fc.name}",
                    }
                )
            )
            func_generator = get_tool(ASSISTANT_NAME, fc.name)
            resp = func_generator(**fc.args)
            await self.websocket.send(
                json.dumps(
                    {
                        "assistant_activity": f"TOOL response - {resp}\n\n\n",
                    }
                )
            )
            function_response = types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response={"result": resp},
                will_continue=False,
            )
            function_responses.append(function_response)
        await self.session.send_tool_response(function_responses=function_responses)

    async def listen_audio_from_websocket(self):
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
        try:
            while True:
                msg = await self.out_queue.get()
                await self.session.send_realtime_input(audio=msg)
        except Exception as e:
            print("Exception while sending audio to gemini - ", e)
            await self.websocket.send(
                json.dumps(
                    {
                        "model_error": f"{e}",
                    }
                )
            )

    async def receive_audio_from_gemini(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if (
                    response.server_content
                    and response.server_content.interrupted is True
                ):
                    print("Interruption detected")
                if response.usage_metadata:
                    usage = response.usage_metadata
                    print("output token usage : ", usage.total_token_count, " tokens")
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
        while True:
            bytestream = await self.audio_in_queue.get()
            base64_audio = base64.b64encode(bytestream).decode("utf-8")
            await self.websocket.send(
                json.dumps(
                    {
                        "audio": base64_audio,
                    }
                )
            )

            """
                Simulate real-time playback duration
                Replace these with actual values

                This is very IMPORTANT becuase websocket.send is async 
                so while True consumes the queue very very fast and all the voice is 
                sent to client, so talk to interrupt doesn't work hence the below code
            """
            sample_rate = 24000  # e.g. 16 kHz
            channels = 1  # mono
            bytes_per_sample = 2  # 16-bit PCM => 2 bytes

            duration_seconds = len(bytestream) / (
                sample_rate * channels * bytes_per_sample
            )

            await asyncio.sleep(duration_seconds)

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
            await self.websocket.send(json.dumps({"model_error": f"{EG}"}))
            traceback.print_exception(EG)


async def gemini_session_handler(websocket):
    print("New client connected - ", websocket.id)
    loop = AudioLoop(websocket)
    await loop.run()


def health_check(connection, request):
    if request.path == "/healthz":
        return connection.respond(http.HTTPStatus.OK, "OK\n")

    if request.path == "/health":
        print("health invoked")
        return connection.respond(http.HTTPStatus.OK, "OK\n")


async def main() -> None:
    try:
        async with websockets.serve(
            gemini_session_handler, "0.0.0.0", 9082, process_request=health_check
        ) as server:
            print("Running websocket server on 0.0.0.0:9082...")
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGTERM, server.close)
            await server.wait_closed()
    except Exception as e:
        print(f"WebSocket server error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Server failed to start: {e}")
