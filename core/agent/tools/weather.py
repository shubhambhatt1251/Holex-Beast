"""Weather data from Open-Meteo (no API key needed)."""

from __future__ import annotations

import logging

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

WEATHER_CODES = {
    0: "☀️ Clear sky", 1: "🌤️ Mainly clear", 2: "⛅ Partly cloudy",
    3: "☁️ Overcast", 45: "🌫️ Foggy", 48: "🌫️ Rime fog",
    51: "🌦️ Light drizzle", 53: "🌦️ Moderate drizzle", 55: "🌧️ Dense drizzle",
    61: "🌧️ Light rain", 63: "🌧️ Moderate rain", 65: "🌧️ Heavy rain",
    71: "🌨️ Light snow", 73: "🌨️ Moderate snow", 75: "❄️ Heavy snow",
    80: "🌦️ Light showers", 81: "🌧️ Moderate showers", 82: "⛈️ Heavy showers",
    95: "⛈️ Thunderstorm", 96: "⛈️ Thunderstorm + hail", 99: "⛈️ Heavy hail",
}


class WeatherTool(BaseTool):
    """Get weather forecast using Open-Meteo. No API key required."""

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return (
            "Get current weather and 3-day forecast for any city. "
            "Returns temperature, conditions, humidity, wind speed."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'New Delhi' or 'London'",
                },
            },
            "required": ["city"],
        }

    async def execute(self, city: str, **kwargs) -> ToolResult:
        try:
            import httpx

            # Step 1: Geocode city name to coordinates
            async with httpx.AsyncClient(timeout=10) as client:
                geo_resp = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "en"},
                )
                geo_data = geo_resp.json()

                if not geo_data.get("results"):
                    return ToolResult(
                        success=False, output="",
                        error=f"City '{city}' not found",
                    )

                loc = geo_data["results"][0]
                lat, lon = loc["latitude"], loc["longitude"]
                city_name = f"{loc['name']}, {loc.get('country', '')}"

                # Step 2: Get weather data
                weather_resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": (
                            "temperature_2m,relative_humidity_2m,"
                            "weather_code,wind_speed_10m,apparent_temperature"
                        ),
                        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                        "timezone": "auto",
                        "forecast_days": 3,
                    },
                )
                data = weather_resp.json()

            current = data["current"]
            daily = data["daily"]

            # Format current weather
            weather_code = current.get("weather_code", 0)
            condition = WEATHER_CODES.get(weather_code, "Unknown")

            output = f"## 🌍 Weather for {city_name}\n\n"
            output += "### Current\n"
            output += f"- {condition}\n"
            temp = current['temperature_2m']
            feels = current['apparent_temperature']
            output += f"- 🌡️ Temperature: **{temp}°C** (feels like {feels}°C)\n"
            output += f"- 💧 Humidity: {current['relative_humidity_2m']}%\n"
            output += f"- 💨 Wind: {current['wind_speed_10m']} km/h\n\n"

            # Format 3-day forecast
            output += "### 3-Day Forecast\n"
            for i in range(min(3, len(daily["time"]))):
                date = daily["time"][i]
                code = daily["weather_code"][i]
                cond = WEATHER_CODES.get(code, "")
                tmax = daily["temperature_2m_max"][i]
                tmin = daily["temperature_2m_min"][i]
                rain = daily["precipitation_probability_max"][i]
                output += f"- **{date}**: {cond} | {tmin}°C - {tmax}°C | Rain: {rain}%\n"

            return ToolResult(success=True, output=output, data=data)

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="httpx not installed. Run: pip install httpx",
            )
        except Exception as e:
            logger.error(f"Weather failed: {e}")
            return ToolResult(success=False, output="", error=str(e))
