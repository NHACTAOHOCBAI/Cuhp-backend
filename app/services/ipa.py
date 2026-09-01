import re
from html.parser import HTMLParser
from typing import Dict
from loguru import logger

try:
    import eng_to_ipa as ipa
except ImportError:
    logger.warning("eng_to_ipa is not installed. IPA transcription will return original text.")
    ipa = None


def _ipa_convert(word_or_phrase: str) -> str:
    """Helper to safely convert word/phrase to IPA while preserving exact line breaks and spaces."""
    if not ipa or not word_or_phrase:
        return word_or_phrase
    try:
        if "\n" in word_or_phrase:
            lines = word_or_phrase.split("\n")
            converted_lines = [_ipa_convert(line) for line in lines]
            return "\n".join(converted_lines)
        if not word_or_phrase.strip():
            return word_or_phrase
        return ipa.convert(word_or_phrase)
    except Exception:
        return word_or_phrase


class IpaHTMLConverter(HTMLParser):
    def __init__(self, mode: str = "phonetic"):
        super().__init__()
        self.mode = mode
        self.result = []

    def handle_starttag(self, tag, attrs):
        attr_str = "".join([f' {k}="{v}"' if v is not None else f" {k}" for k, v in attrs])
        self.result.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        self.result.append(f"</{tag}>")

    def handle_data(self, data):
        if not data:
            return
        if self.mode == "phonetic":
            self.result.append(_ipa_convert(data))
        elif self.mode == "interlinear":
            tokens = re.split(r"(\b[a-zA-Z']+\b)", data)
            for token in tokens:
                if re.match(r"^[a-zA-Z']+$", token):
                    phonetic = _ipa_convert(token)
                    self.result.append(
                        f'<ruby class="ipa-ruby">{token}<rt class="ipa-phonetic">/{phonetic}/</rt></ruby>'
                    )
                else:
                    self.result.append(token)
        else:
            self.result.append(data)

    def handle_entityref(self, name):
        self.result.append(f"&{name};")

    def handle_charref(self, name):
        self.result.append(f"&#{name};")

    def get_html(self) -> str:
        return "".join(self.result)


def convert_text_to_ipa(text: str, mode: str = "phonetic") -> str:
    """Convert raw text or HTML content to IPA transcription."""
    if not text or not text.strip():
        return ""

    has_html = bool(re.search(r"<[a-zA-Z][\s\S]*>", text))
    if has_html:
        parser = IpaHTMLConverter(mode=mode)
        parser.feed(text)
        return parser.get_html()
    else:
        if mode == "phonetic":
            return _ipa_convert(text)
        elif mode == "interlinear":
            lines = text.split("\n")
            converted_lines = []
            for line in lines:
                tokens = re.split(r"(\b[a-zA-Z']+\b)", line)
                out = []
                for token in tokens:
                    if re.match(r"^[a-zA-Z']+$", token):
                        phonetic = _ipa_convert(token)
                        out.append(f'<ruby class="ipa-ruby">{token}<rt class="ipa-phonetic">/{phonetic}/</rt></ruby>')
                    else:
                        out.append(token)
                converted_lines.append("".join(out))
            return "\n".join(converted_lines)
        return text


def get_all_ipa_formats(text: str) -> Dict[str, str]:
    """Return both phonetic and interlinear IPA formats."""
    if not text or not text.strip():
        return {"phonetic": "", "interlinear": ""}
    return {
        "phonetic": convert_text_to_ipa(text, mode="phonetic"),
        "interlinear": convert_text_to_ipa(text, mode="interlinear"),
    }
