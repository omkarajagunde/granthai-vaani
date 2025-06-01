## pip install google-genai==0.3.0

import asyncio
import json
import os
import websockets
from google import genai
import base64
from google.genai import types
from tools import get_tool
from prompts import get_prompt, get_tool_config

# MODEL = "gemini-2.0-flash-exp"  # use your model ID
MODEL = "gemini-2.0-flash-live-001"
ASSISTANT_NAME = "yoda_diagnostics"
SYSTEM_PROMPT = get_prompt(ASSISTANT_NAME)
TOOL_CONFIG = get_tool_config(ASSISTANT_NAME)

client = genai.Client(
    api_key="YOUR KEY HERE",
    http_options={
        "api_version": "v1beta",
    },
)

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
    # realtime_input_config=types.RealtimeInputConfig(
    #     turn_coverage="TURN_INCLUDES_ALL_INPUT"
    # ),
    system_instruction=SYSTEM_PROMPT,
    tools=[TOOL_CONFIG],
)


async def gemini_session_handler(client_websocket):
    """Handles the interaction with Gemini API within a websocket session.

    Args:
        client_websocket: The websocket connection to the client.
    """
    try:
        async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
            print("Connected to Gemini API")

            async def send_to_gemini():
                """Sends messages from the client websocket to the Gemini API."""
                try:
                    async for message in client_websocket:
                        try:
                            data = json.loads(message)
                            if "realtime_input" in data:
                                for chunk in data["realtime_input"]["media_chunks"]:
                                    if chunk["mime_type"] == "audio/pcm":
                                        print("Sending...")
                                        await session.send_realtime_input(
                                            audio={
                                                "mime_type": "audio/pcm",
                                                "data": chunk["data"],
                                            }
                                        )

                        except Exception as e:
                            print(f"Error sending to Gemini: {e}")
                    print("Client connection closed (send)")
                except Exception as e:
                    print(f"Error sending to Gemini: {e}")
                finally:
                    print("send_to_gemini closed")

            async def receive_from_gemini():
                """Receives responses from the Gemini API and forwards them to the client, looping until turn is complete."""
                try:
                    while True:
                        try:
                            print("receiving from gemini")
                            async for response in session.receive():
                                print("response - ", response)
                                # first_response = True
                                # print(f"response: {response}")
                                if response.server_content is None:
                                    if response.tool_call is not None:
                                        # handle the tool call
                                        function_responses = []

                                        for fc in response.tool_call.function_calls:
                                            print("TOOL Used: ", fc.name)
                                            func_generator = get_tool(
                                                ASSISTANT_NAME, fc.name
                                            )
                                            resp = func_generator(**fc.args)
                                            function_response = types.FunctionResponse(
                                                id=fc.id,
                                                name=fc.name,
                                                response={"result": resp},
                                                will_continue=False,
                                            )
                                            function_responses.append(function_response)
                                        await session.send_tool_response(
                                            function_responses=function_responses
                                        )
                                        continue

                                    # print(f'Unhandled server message! - {response}')
                                    # continue

                                model_turn = response.server_content.model_turn
                                if model_turn:
                                    for part in model_turn.parts:
                                        # print(f"part: {part}")
                                        if (
                                            hasattr(part, "text")
                                            and part.text is not None
                                        ):
                                            # print(f"text: {part.text}")
                                            await client_websocket.send(
                                                json.dumps({"text": part.text})
                                            )
                                        elif (
                                            hasattr(part, "inline_data")
                                            and part.inline_data is not None
                                        ):
                                            # if first_response:
                                            # print("audio mime_type:", part.inline_data.mime_type)
                                            # first_response = False
                                            base64_audio = base64.b64encode(
                                                part.inline_data.data
                                            ).decode("utf-8")
                                            await client_websocket.send(
                                                json.dumps(
                                                    {
                                                        "audio": base64_audio,
                                                    }
                                                )
                                            )
                                            print("audio received")

                                if response.server_content.turn_complete:
                                    print("\n<Turn complete>")
                        except websockets.exceptions.ConnectionClosedOK:
                            print("Client connection closed normally (receive)")
                            break  # Exit the loop if the connection is closed
                        except Exception as e:
                            print(f"Error receiving from Gemini: {e}")
                            break  # exit the lo

                except Exception as e:
                    print(f"Error receiving from Gemini: {e}")
                finally:
                    print("Gemini connection closed (receive)")

            # Start send loop
            send_task = asyncio.create_task(send_to_gemini())
            # Launch receive loop as a background task
            receive_task = asyncio.create_task(receive_from_gemini())
            await asyncio.gather(send_task, receive_task)

    except Exception as e:
        print(f"Error in Gemini session: {e}")
    finally:
        print("Gemini session closed.")


async def main() -> None:
    async with websockets.serve(gemini_session_handler, "localhost", 9082):
        print("Running websocket server localhost:9082...")
        await asyncio.Future()  # Keep the server running indefinitely


if __name__ == "__main__":
    asyncio.run(main())
