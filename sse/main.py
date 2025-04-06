import asyncio
import os

from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.sse import sse_client

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


async def run():
    async with sse_client("http://localhost:8080/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            prompt = "What is the weather in London?"
            await session.initialize()

            # Get tools from MCP session and convert to Gemini Tool objects
            mcp_tools = await session.list_tools()
            tools = [
                types.Tool(
                    function_declarations=[
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                k: v
                                for k, v in tool.inputSchema.items()
                                if k not in ["additionalProperties", "$schema"]
                            },
                        }
                    ]
                )
                for tool in mcp_tools.tools
            ]
            # Send request to the model with MCP function declarations
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    tools=tools,
                ),
            )

            # Check for a function call
            if response.candidates[0].content.parts[0].function_call:
                function_call = response.candidates[0].content.parts[0].function_call
                print(function_call)
                # Call the MCP server with the predicted tool
                result = await session.call_tool(
                    function_call.name, arguments=function_call.args
                )
                print(result.content[0].text)
                # Continue as shown in step 4 of "How Function Calling Works"
                # and create a user friendly response
            else:
                print("No function call found in the response.")
                print(response.text)


# Start the asyncio event loop and run the main function
asyncio.run(run())
