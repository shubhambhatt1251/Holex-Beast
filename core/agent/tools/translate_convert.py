"""Translation, unit conversion, and dictionary tool.

Three capabilities in one tool:
- Translate text between 100+ languages
- Convert units (length, weight, temperature, currency, etc.)
- Dictionary lookups (definition, synonyms)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# ── Unit conversion tables ──

_LENGTH = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
}

_WEIGHT = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 1e-6, "milligram": 1e-6, "milligrams": 1e-6,
    "lb": 0.453592, "pound": 0.453592, "pounds": 0.453592,
    "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
    "ton": 907.185, "tons": 907.185,
    "tonne": 1000.0, "tonnes": 1000.0,
}

_VOLUME = {
    "l": 1.0, "liter": 1.0, "liters": 1.0, "litre": 1.0,
    "ml": 0.001, "milliliter": 0.001, "milliliters": 0.001,
    "gal": 3.78541, "gallon": 3.78541, "gallons": 3.78541,
    "qt": 0.946353, "quart": 0.946353, "quarts": 0.946353,
    "cup": 0.236588, "cups": 0.236588,
    "fl oz": 0.0295735, "fluid ounce": 0.0295735,
}

_SPEED = {
    "m/s": 1.0, "mps": 1.0,
    "km/h": 0.277778, "kph": 0.277778, "kmh": 0.277778,
    "mph": 0.44704,
    "knot": 0.514444, "knots": 0.514444,
}

_DATA = {
    "b": 1, "byte": 1, "bytes": 1,
    "kb": 1024, "kilobyte": 1024,
    "mb": 1024**2, "megabyte": 1024**2,
    "gb": 1024**3, "gigabyte": 1024**3,
    "tb": 1024**4, "terabyte": 1024**4,
}

_TIME_UNITS = {
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "day": 86400.0, "days": 86400.0,
    "week": 604800.0, "weeks": 604800.0,
    "month": 2592000.0, "months": 2592000.0,
    "year": 31536000.0, "years": 31536000.0,
}

# Group all non-temperature tables
_CONVERSION_TABLES = [
    ("length", _LENGTH),
    ("weight", _WEIGHT),
    ("volume", _VOLUME),
    ("speed", _SPEED),
    ("data", _DATA),
    ("time", _TIME_UNITS),
]


def _convert_temperature(value: float, from_u: str, to_u: str) -> Optional[float]:
    """Handle temperature conversions."""
    f = from_u.lower().rstrip("°").strip()
    t = to_u.lower().rstrip("°").strip()
    # Normalize
    f_map = {"c": "c", "celsius": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}
    f = f_map.get(f)
    t = f_map.get(t)
    if not f or not t:
        return None
    # Convert to Celsius first
    if f == "c":
        c = value
    elif f == "f":
        c = (value - 32) * 5 / 9
    else:
        c = value - 273.15
    # Convert from Celsius
    if t == "c":
        return round(c, 2)
    elif t == "f":
        return round(c * 9 / 5 + 32, 2)
    else:
        return round(c + 273.15, 2)


def _convert_units(value: float, from_unit: str, to_unit: str) -> Optional[str]:
    """Attempt conversion across all unit tables."""
    fl = from_unit.lower().strip()
    tl = to_unit.lower().strip()

    # Temperature
    temp_result = _convert_temperature(value, fl, tl)
    if temp_result is not None:
        return f"**{value} {from_unit}** = **{temp_result} {to_unit}**"

    # Standard tables
    for category, table in _CONVERSION_TABLES:
        if fl in table and tl in table:
            # Convert through base unit
            base_value = value * table[fl]
            result = base_value / table[tl]
            # Clean up decimal
            if result == int(result):
                result = int(result)
            else:
                result = round(result, 6)
            return f"**{value} {from_unit}** = **{result} {to_unit}**"

    return None


# ── Language codes for translation ──

LANG_CODES = {
    "english": "en", "hindi": "hi", "spanish": "es", "french": "fr",
    "german": "de", "italian": "it", "portuguese": "pt", "russian": "ru",
    "japanese": "ja", "korean": "ko", "chinese": "zh-CN", "arabic": "ar",
    "bengali": "bn", "tamil": "ta", "telugu": "te", "marathi": "mr",
    "gujarati": "gu", "kannada": "kn", "malayalam": "ml", "punjabi": "pa",
    "urdu": "ur", "dutch": "nl", "turkish": "tr", "vietnamese": "vi",
    "thai": "th", "swedish": "sv", "polish": "pl", "romanian": "ro",
    "czech": "cs", "greek": "el", "hebrew": "he", "indonesian": "id",
    "malay": "ms", "persian": "fa", "ukrainian": "uk", "swahili": "sw",
    "nepali": "ne", "sinhala": "si", "burmese": "my",
}


class TranslateConvertTool(BaseTool):
    """Translate text, convert units, and look up words."""

    @property
    def name(self) -> str:
        return "translate_convert"

    @property
    def description(self) -> str:
        return (
            "Three capabilities: "
            "1) Translate text between any two languages "
            "(e.g., 'translate hello to Hindi'). "
            "2) Convert units (length, weight, temperature, volume, "
            "speed, data, time — e.g., '5 miles to km', '100°F to °C'). "
            "3) Dictionary lookup (definition and synonyms)."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["translate", "convert", "define"],
                    "description": "translate, convert (units), or define (dictionary).",
                },
                "text": {
                    "type": "string",
                    "description": "Text to translate, word to define, or conversion expression.",
                },
                "from_lang": {
                    "type": "string",
                    "description": "Source language for translation (e.g., 'english', 'en').",
                },
                "to_lang": {
                    "type": "string",
                    "description": "Target language for translation (e.g., 'hindi', 'hi').",
                },
                "value": {
                    "type": "number",
                    "description": "Numeric value for unit conversion.",
                },
                "from_unit": {
                    "type": "string",
                    "description": "Source unit (e.g., 'miles', 'kg', '°F').",
                },
                "to_unit": {
                    "type": "string",
                    "description": "Target unit (e.g., 'km', 'pounds', '°C').",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        text: str = "",
        from_lang: str = "en",
        to_lang: str = "en",
        value: float = 0,
        from_unit: str = "",
        to_unit: str = "",
        target: str = "",
        **kw,
    ) -> ToolResult:
        # LLM sometimes sends 'target' instead of 'text'
        text = text or target
        if action == "translate":
            return await self._translate(text, from_lang, to_lang)
        elif action == "convert":
            return self._convert(value or 0, from_unit, to_unit, text)
        elif action == "define":
            return await self._define(text)
        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    async def _translate(self, text: str, src: str, dest: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, output="", error="No text to translate.")

        # Resolve language names to codes
        src_code = LANG_CODES.get(src.lower().strip(), src.lower().strip())
        dest_code = LANG_CODES.get(dest.lower().strip(), dest.lower().strip())

        # Try deep_translator (pip install deep-translator)
        try:
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(source=src_code, target=dest_code).translate(text)
            return ToolResult(
                success=True,
                output=f"**{src}** → **{dest}**:\n\n> {result}",
            )
        except ImportError:
            pass

        # Fallback: googletrans
        try:
            from googletrans import Translator
            translator = Translator()
            result = translator.translate(text, src=src_code, dest=dest_code)
            return ToolResult(
                success=True,
                output=f"**{src}** → **{dest}**:\n\n> {result.text}",
            )
        except ImportError:
            pass

        return ToolResult(
            success=False, output="",
            error="Install a translation package: pip install deep-translator",
        )

    def _convert(self, value: float, from_u: str, to_u: str, text: str) -> ToolResult:
        # If value/units weren't passed separately, try parsing from text
        if (not from_u or not to_u) and text:
            m = re.match(
                r'([\d.]+)\s*([a-zA-Z°/]+)\s+(?:to|in|=)\s+([a-zA-Z°/]+)',
                text.strip(),
            )
            if m:
                value = float(m.group(1))
                from_u = m.group(2)
                to_u = m.group(3)

        if not from_u or not to_u:
            return ToolResult(success=False, output="", error="Need value, from_unit, and to_unit.")

        result = _convert_units(value, from_u, to_u)
        if result:
            return ToolResult(success=True, output=result)
        return ToolResult(
            success=False, output="",
            error=f"Cannot convert from '{from_u}' to '{to_u}'. Units not recognized or incompatible.",
        )

    async def _define(self, word: str) -> ToolResult:
        if not word:
            return ToolResult(success=False, output="", error="No word to define.")

        # Try Free Dictionary API
        try:
            import json
            import urllib.request
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.strip()}"
            req = urllib.request.Request(url, headers={"User-Agent": "Holex/1.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode())

            if isinstance(data, list) and data:
                entry = data[0]
                lines = [f"**{entry.get('word', word)}**"]
                if entry.get("phonetic"):
                    lines[0] += f" ({entry['phonetic']})"

                for meaning in entry.get("meanings", [])[:3]:
                    pos = meaning.get("partOfSpeech", "")
                    lines.append(f"\n*{pos}*")
                    for d in meaning.get("definitions", [])[:2]:
                        lines.append(f"- {d['definition']}")
                        if d.get("example"):
                            lines.append(f"  *\"{d['example']}\"*")

                    syns = meaning.get("synonyms", [])[:5]
                    if syns:
                        lines.append(f"  Synonyms: {', '.join(syns)}")

                return ToolResult(success=True, output="\n".join(lines))
        except Exception:
            pass

        return ToolResult(
            success=False, output="",
            error=f"Could not find definition for '{word}'",
        )
