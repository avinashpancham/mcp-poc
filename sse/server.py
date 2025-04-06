import json
from datetime import datetime

import httpx
import mcp.types as types
import uvicorn
from geopy.geocoders import Nominatim
from mcp.server.lowlevel import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route

geolocator = Nominatim(user_agent="mcp_demo")


async def fetch_weather(
    city: str,
) -> list[types.TextContent]:
    headers = {
        "User-Agent": "MCP Test Server (github.com/modelcontextprotocol/python-sdk)"
    }
    today = datetime.now().strftime("%Y-%m-%d")

    location = geolocator.geocode(city)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={location.latitude}&longitude={location.longitude}&current=temperature_2m&hourly=temperature_2m&start_date={today}&end_date={today}"
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()

        hourly = response.json()["hourly"]
        temperature = {
            time: temp for time, temp in zip(hourly["time"], hourly["temperature_2m"])
        }

        return [types.TextContent(type="text", text=json.dumps(temperature))]


def main() -> int:
    app = Server("mcp-weather-fetcher")

    @app.call_tool()
    async def fetch_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name != "fetch":
            raise ValueError(f"Unknown tool: {name}")
        if "city" not in arguments:
            raise ValueError("Missing required argument 'city'")
        return await fetch_weather(arguments["city"])

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="fetch",
                description="Fetches the weather for a city and returns it",
                inputSchema={
                    "type": "object",
                    "required": ["city"],
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City for which we need to fetch the weather",
                        }
                    },
                },
            )
        ]

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    starlette_app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    uvicorn.run(starlette_app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
