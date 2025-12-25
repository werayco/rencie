import re, json


def soParser(text: str):
    text = text.strip()

    def clean_json_string(match):
        return match.group(0).replace("\n", " ").replace("\r", "")

    try:
        pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_text = match.group(1).strip()
            json_text = re.sub(r'"[^"]*"', clean_json_string, json_text)
            return json.loads(json_text)
    except Exception as e:
        pass
    try:
        if text.startswith("{") and text.endswith("}"):
            cleaned_text = re.sub(r'"[^"]*"', clean_json_string, text)
            return json.loads(cleaned_text)
    except Exception as e:
        pass
    try:
        pattern = r"(\{.*\})"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_text = match.group(1).strip()
            json_text = re.sub(r'"[^"]*"', clean_json_string, json_text)
            return json.loads(json_text)
    except Exception as e:
        pass
    return {
        "error": "Failed to parse JSON from the response.",
    }
