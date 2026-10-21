"""ELIN v5 · entorno limpio y centrado, con presentación y origen de cada imagen.

- Fondo claro sólido con una trama de hojas dibujadas a línea, casi imperceptible.
- Todo en el centro: selector de modo, chat, menús de opciones y resultados.
- Presentación con barra de carga, botones de minimizar/maximizar (y F11).
- Cada imagen indica dónde se creó o se buscó y si usó aprendizaje automático o solo Python.
- Las imágenes (creadas con IA, con recursos de Python o buscadas en internet) aparecen
  dentro de la propia conversación; al pulsarlas se abren en grande.

Claves opcionales (variables de entorno)
  POLLINATIONS_API_KEY, HF_TOKEN, HORDE_API_KEY, PEXELS_API_KEY, UNSPLASH_ACCESS_KEY
  GOOGLE_CSE_API_KEY y GOOGLE_CSE_ID (solo cuentas con acceso a Custom Search JSON API)

Comandos del chat:
  buscar audio: término | generar audio: texto para convertirlo en MP3
"""
from __future__ import annotations

import base64
import colorsys
import hashlib
import importlib.util
import io
import itertools
import math
import os
import queue
import random
import re
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Callable

import pygame
import requests
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFilter

# ----------------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------------
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 820
MIN_WIDTH = 900
MIN_HEIGHT = 660
STEP_MIN = 0.55        # segundos mínimos por paso de la barra de carga
MIN_INTRO = 3.0        # duración mínima de la presentación
COL_MAX = 880          # ancho de la columna central
HEADER_H = 60          # alto de la barra superior
PLANT_INK = (233, 229, 219)   # color de la trama de plantas (casi igual al fondo)
MAX_INPUT = 2000
REQUEST_TIMEOUT = 45
# Las rutas se anclan al proyecto, no a la carpeta desde la que se ejecuta Python.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = (os.path.dirname(SCRIPT_DIR)
               if os.path.basename(SCRIPT_DIR).lower() == "elin" else SCRIPT_DIR)
SAVE_DIR = os.path.join(PROJECT_DIR, "imagenes_elin")
AUDIO_DIR = os.path.join(PROJECT_DIR, "audios_elin")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")

TEXT_ENDPOINT = "https://text.pollinations.ai/"
IMAGE_ENDPOINT = "https://image.pollinations.ai/prompt/"
GEN_BASE = "https://gen.pollinations.ai"
SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
HORDE_BASE = "https://stablehorde.net/api/v2"
HF_MODEL = os.environ.get("ELIN_HF_MODEL", "black-forest-labs/FLUX.1-schnell")
HF_BASE = "https://router.huggingface.co/hf-inference/models/"
LOCAL_MODEL = os.environ.get("ELIN_LOCAL_MODEL", "stabilityai/sd-turbo")
OLLAMA_BASE = os.environ.get("ELIN_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("ELIN_OLLAMA_MODEL", "qwen2.5:3b")
ALT_POLLINATIONS_MODEL = os.environ.get("ELIN_ALT_MODEL", "turbo")
FORCE_LOCAL = os.environ.get("ELIN_FORCE_LOCAL") == "1"
HEADERS = {"User-Agent": "ELIN-Desktop/3.0 (proyecto educativo)"}

C = {
    "bg": (247, 245, 241),
    "panel": (255, 255, 255),
    "soft": (241, 238, 232),
    "border": (229, 224, 216),
    "text": (38, 34, 31),
    "muted": (134, 127, 118),
    "accent": (233, 106, 62),
    "accent_hover": (242, 128, 86),
    "accent_soft": (253, 235, 226),
    "on_accent": (255, 255, 255),
    "danger": (214, 69, 69),
    "ok": (62, 160, 120),
    "off": (200, 194, 186),
}

FONT_BODY = ["segoeui", "helveticaneue", "ubuntu", "arial", "dejavusans"]
FONT_DISPLAY = ["bahnschrift", "segoeuisemibold", "segoeui", "arial", "dejavusans"]

# Gradientes pastel -> saturado para los mosaicos de imagen de los botones.
TILE_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "default": ((196, 190, 182), (150, 142, 132)),
    "logo": ((255, 190, 120), (236, 96, 70)),
    "chat": ((255, 205, 170), (255, 132, 104)),
    "create": ((255, 224, 140), (248, 148, 60)),
    "search": ((170, 224, 212), (66, 158, 170)),
    "plus": ((214, 206, 255), (140, 120, 235)),
    "download": ((190, 226, 190), (80, 170, 120)),
    "refresh": ((255, 226, 170), (240, 160, 70)),
    "trash": ((255, 200, 200), (226, 92, 92)),
    "link": ((190, 214, 250), (84, 134, 226)),
    "globe": ((190, 214, 250), (84, 134, 226)),
    "wand": ((236, 206, 255), (172, 110, 232)),
    "copy": ((206, 214, 230), (120, 136, 170)),
    "speaker": ((255, 214, 196), (240, 120, 96)),
    "stop": ((255, 200, 200), (226, 92, 92)),
    "auto": ((255, 214, 150), (244, 140, 60)),
    "compare": ((206, 196, 255), (126, 108, 232)),
    "flux": ((255, 200, 168), (238, 102, 70)),
    "turbo": ((255, 232, 150), (240, 170, 40)),
    "horde": ((176, 224, 200), (60, 160, 130)),
    "hf": ((255, 232, 150), (236, 160, 40)),
    "local": ((200, 210, 232), (100, 118, 168)),
    "openverse": ((255, 205, 160), (232, 112, 60)),
    "wikimedia": ((190, 214, 250), (70, 120, 210)),
    "pexels": ((176, 226, 206), (50, 160, 130)),
    "unsplash": ((214, 214, 222), (100, 100, 116)),
    "procedural": ((214, 208, 198), (128, 120, 110)),
}
TILE_LETTERS = {
    "auto": "A", "compare": "C", "flux": "F", "turbo": "T", "horde": "H", "hf": "HF", "local": "L",
    "openverse": "O", "wikimedia": "W", "pexels": "P", "unsplash": "U", "procedural": "Py",
}
ICON_FOR = {"create": "image", "logo": "image"}

PROVIDER_LABELS = {
    "flux": "Pollinations Flux",
    "turbo": "Pollinations Turbo",
    "horde": "Stable Horde",
    "hf": "Hugging Face",
    "local": "IA local",
    "procedural": "Arte generativo",
}
def provider_origin(key: str) -> tuple[str, str]:
    """(tipo, descripción) de dónde se creó una imagen. tipo: ml | ml_local | python."""
    return {
        "flux": ("ml", "Servicio en línea · Pollinations (modelo Flux)"),
        "turbo": ("ml", f"Servicio en línea · Pollinations (modelo {ALT_POLLINATIONS_MODEL})"),
        "horde": ("ml", "Servicio en línea · Stable Horde (Stable Diffusion en GPUs comunitarias)"),
        "hf": ("ml", f"Servicio en línea · Hugging Face ({HF_MODEL.split('/')[-1]})"),
        "local": ("ml_local", f"En tu equipo · PyTorch + diffusers ({LOCAL_MODEL.split('/')[-1]})"),
        "procedural": ("python", "Recursos de Python · Pillow (arte generativo)"),
    }[key]


ORIGIN_BADGE = {
    "ml": "Aprendizaje automático",
    "ml_local": "Aprendizaje automático · local",
    "python": "Python · sin aprendizaje automático",
    "search": "Búsqueda en internet · no generada",
}
ORIGIN_COLORS = {
    "ml": ((253, 235, 226), (222, 96, 52)),
    "ml_local": ((224, 243, 235), (46, 140, 104)),
    "python": ((238, 235, 229), (118, 111, 103)),
    "search": ((228, 238, 252), (62, 112, 204)),
}
CHAT_ORIGIN = "modelo de lenguaje · aprendizaje automático"

PROVIDER_CHIPS = [("auto", "Auto"), ("compare", "Comparar"), ("flux", "Flux"), ("turbo", "Turbo"),
                  ("horde", "Horde"), ("hf", "Hugging Face"), ("local", "Local")]
STYLES = [
    ("none", "Sin estilo", ""),
    ("photo", "Realista", "photorealistic, natural light, high detail"),
    ("illustration", "Ilustración", "digital illustration, clean lines, vibrant colors"),
    ("watercolor", "Acuarela", "soft watercolor painting, paper texture"),
    ("3d", "3D", "3D render, soft studio lighting, smooth materials"),
    ("anime", "Anime", "anime style, detailed, vibrant colors"),
    ("minimal", "Minimal", "minimalist composition, flat design, negative space"),
]
FORMATS = [("square", "Cuadrada", (768, 768)), ("wide", "Horizontal", (1024, 640)), ("tall", "Vertical", (640, 1024))]

CHIPS = [   # (etiqueta, modo, texto inicial, icono)
    ("Explícame algo", "chat", "Explícame de forma sencilla ", "chat"),
    ("Ideas creativas", "chat", "Dame 5 ideas creativas para ", "wand"),
    ("Crear una imagen", "create", "Un faro minimalista sobre un acantilado al amanecer, tonos cálidos", "create"),
    ("Buscar fotos", "search", "paisaje de montaña", "search"),
    ("Generar audio", "chat", "generar audio: ", "speaker"),
]

SYSTEM_INSTRUCTIONS = (
    "Eres ELIN, un asistente útil que responde en español claro y cercano. Contesta la petición del usuario. "
    "No afirmes haber verificado hechos que no aparecen en el contexto. Si hay contexto web, úsalo con cautela "
    "y termina con una sección breve 'Fuentes consultadas' que enumere título y URL. Si no hay resultados web, "
    "responde con la cautela apropiada. No inventes citas."
)
ENHANCE_INSTRUCTIONS = (
    "Reescribe la idea del usuario como un prompt para un generador de imágenes. Responde SOLO con el prompt, "
    "en inglés, de máximo 60 palabras: sujeto, entorno, iluminación, estilo y composición. Sin comillas ni explicaciones."
)


# ----------------------------------------------------------------------------
# Modelos de datos
# ----------------------------------------------------------------------------
@dataclass
class Message:
    role: str
    text: str
    stamp: str
    meta: bool = False     # mensajes de sistema que no se envían a la IA
    origin: str = ""
    cache_key: int = -1
    lines: list[str] = field(default_factory=list)


@dataclass(eq=False)
class GalleryItem:
    pil: Image.Image
    surface: pygame.Surface
    prompt: str
    full_prompt: str
    provider_label: str
    request_provider: str
    size: tuple[int, int]
    used_key: str = "procedural"   # motor que realmente la creó


@dataclass(eq=False)
class SearchResult:
    title: str
    thumb_url: str
    full_url: str
    page_url: str
    creator: str
    license: str
    source: str
    surface: pygame.Surface | None = None
    failed: bool = False
    full_surface: pygame.Surface | None = None
    full_loading: bool = False


# ----------------------------------------------------------------------------
# Iconos vectoriales (se dibujan sobre cualquier Surface)
# ----------------------------------------------------------------------------
def draw_icon(d: pygame.Surface, name: str, cx: int, cy: int, color: tuple[int, int, int], s: int = 8, w: int | None = None) -> None:
    u = s / 8
    w = w or max(1, round(s / 4))

    def p(n: float) -> int:
        return int(round(n * u))

    if name == "chat":
        r = pygame.Rect(0, 0, p(20), p(14))
        r.center = (cx, cy - p(1))
        pygame.draw.rect(d, color, r, w, border_radius=p(5))
        pygame.draw.polygon(d, color, [(cx - p(6), cy + p(5)), (cx - p(1), cy + p(5)), (cx - p(6), cy + p(10))])
    elif name == "image":
        r = pygame.Rect(0, 0, p(20), p(16))
        r.center = (cx, cy)
        pygame.draw.rect(d, color, r, w, border_radius=p(4))
        pygame.draw.lines(d, color, False, [(cx - p(8), cy + p(5)), (cx - p(3), cy - p(1)), (cx + p(1), cy + p(3)), (cx + p(4), cy), (cx + p(8), cy + p(5))], w)
        pygame.draw.circle(d, color, (cx + p(5), cy - p(4)), max(1, p(2)))
    elif name == "search":
        pygame.draw.circle(d, color, (cx - p(2), cy - p(2)), p(6), w)
        pygame.draw.line(d, color, (cx + p(2), cy + p(2)), (cx + p(8), cy + p(8)), w)
    elif name == "plus":
        pygame.draw.line(d, color, (cx - p(7), cy), (cx + p(7), cy), w)
        pygame.draw.line(d, color, (cx, cy - p(7)), (cx, cy + p(7)), w)
    elif name == "send":
        pygame.draw.line(d, color, (cx, cy + p(7)), (cx, cy - p(7)), w)
        pygame.draw.lines(d, color, False, [(cx - p(6), cy - p(1)), (cx, cy - p(7)), (cx + p(6), cy - p(1))], w)
    elif name == "copy":
        pygame.draw.rect(d, color, pygame.Rect(cx - p(2), cy - p(7), p(9), p(11)), w, border_radius=p(2))
        pygame.draw.rect(d, color, pygame.Rect(cx - p(7), cy - p(3), p(9), p(11)), w, border_radius=p(2))
    elif name == "speaker":
        pygame.draw.polygon(d, color, [(cx - p(8), cy - p(3)), (cx - p(4), cy - p(3)), (cx, cy - p(7)), (cx, cy + p(7)), (cx - p(4), cy + p(3)), (cx - p(8), cy + p(3))])
        pygame.draw.arc(d, color, pygame.Rect(cx - p(3), cy - p(5), p(10), p(10)), -1.0, 1.0, w)
        pygame.draw.arc(d, color, pygame.Rect(cx - p(5), cy - p(8), p(16), p(16)), -1.0, 1.0, w)
    elif name == "stop":
        pygame.draw.rect(d, color, pygame.Rect(cx - p(6), cy - p(6), p(12), p(12)), border_radius=p(2))
    elif name == "download":
        pygame.draw.line(d, color, (cx, cy - p(7)), (cx, cy + p(3)), w)
        pygame.draw.lines(d, color, False, [(cx - p(5), cy - p(2)), (cx, cy + p(4)), (cx + p(5), cy - p(2))], w)
        pygame.draw.line(d, color, (cx - p(7), cy + p(7)), (cx + p(7), cy + p(7)), w)
    elif name == "close":
        pygame.draw.line(d, color, (cx - p(5), cy - p(5)), (cx + p(5), cy + p(5)), w)
        pygame.draw.line(d, color, (cx - p(5), cy + p(5)), (cx + p(5), cy - p(5)), w)
    elif name == "refresh":
        pygame.draw.arc(d, color, pygame.Rect(cx - p(7), cy - p(7), p(14), p(14)), 0.7, 5.6, w)
        # punta de flecha al final del arco, apuntando en el sentido de giro
        sx, sy = cx + 0.765 * p(7), cy - 0.644 * p(7)
        tx, ty, nx, ny = 0.644, 0.765, 0.765, -0.644
        pygame.draw.polygon(d, color, [(sx + tx * p(4.5), sy + ty * p(4.5)),
                                       (sx + nx * p(3.6), sy + ny * p(3.6)),
                                       (sx - nx * p(3.6), sy - ny * p(3.6))])
    elif name == "globe":
        pygame.draw.circle(d, color, (cx, cy), p(7), w)
        pygame.draw.ellipse(d, color, pygame.Rect(cx - p(3), cy - p(7), p(6), p(14)), max(1, w // 2))
        pygame.draw.line(d, color, (cx - p(7), cy), (cx + p(7), cy), max(1, w // 2))
    elif name == "down":
        pygame.draw.lines(d, color, False, [(cx - p(6), cy - p(3)), (cx, cy + p(4)), (cx + p(6), cy - p(3))], w)
    elif name == "wand":
        pygame.draw.polygon(d, color, [(cx, cy - p(8)), (cx + p(2), cy - p(2)), (cx + p(8), cy), (cx + p(2), cy + p(2)),
                                      (cx, cy + p(8)), (cx - p(2), cy + p(2)), (cx - p(8), cy), (cx - p(2), cy - p(2))])
    elif name == "link":
        pygame.draw.rect(d, color, pygame.Rect(cx - p(7), cy - p(5), p(11), p(11)), w, border_radius=p(2))
        pygame.draw.line(d, color, (cx - p(1), cy + p(1)), (cx + p(7), cy - p(7)), w)
        pygame.draw.lines(d, color, False, [(cx + p(2), cy - p(7)), (cx + p(7), cy - p(7)), (cx + p(7), cy - p(2))], w)
    elif name == "check":
        pygame.draw.lines(d, color, False, [(cx - p(6), cy), (cx - p(2), cy + p(4)), (cx + p(6), cy - p(5))], w)
    elif name == "minimize":
        pygame.draw.line(d, color, (cx - p(6), cy + p(3)), (cx + p(6), cy + p(3)), w)
    elif name == "maximize":
        pygame.draw.rect(d, color, pygame.Rect(cx - p(6), cy - p(6), p(12), p(12)), w, border_radius=p(2))
    elif name == "restore":
        pygame.draw.rect(d, color, pygame.Rect(cx - p(6), cy - p(3), p(9), p(9)), w, border_radius=p(2))
        pygame.draw.lines(d, color, False, [(cx - p(2), cy - p(3)), (cx - p(2), cy - p(7)), (cx + p(6), cy - p(7)), (cx + p(6), cy + p(1)), (cx + p(3), cy + p(1))], w)
    elif name == "trash":
        pygame.draw.rect(d, color, pygame.Rect(cx - p(5), cy - p(3), p(10), p(11)), w, border_radius=p(2))
        pygame.draw.line(d, color, (cx - p(7), cy - p(4)), (cx + p(7), cy - p(4)), w)
        pygame.draw.line(d, color, (cx - p(2), cy - p(7)), (cx + p(2), cy - p(7)), w)


# ----------------------------------------------------------------------------
# Utilidades de texto
# ----------------------------------------------------------------------------
def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                    current = ""
                while word and font.size(word)[0] > max_width:
                    cut = len(word)
                    while cut > 1 and font.size(word[:cut])[0] > max_width:
                        cut -= 1
                    lines.append(word[:cut])
                    word = word[cut:]
                current = word
        if current:
            lines.append(current)
    return lines


def wrap_input(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    lines = wrap_text(text, font, max_width)
    if text.endswith("\n"):
        lines.append("")
    return lines or [""]


def fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text
    while text and font.size(text + "…")[0] > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def clean_prompt(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = text.replace("`", "")
    out = []
    for line in text.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*[-*]\s+", "• ", line)
        out.append(line)
    return "\n".join(out)


def fit_size(w: int, h: int, max_side: int, mult: int) -> tuple[int, int]:
    scale = min(1.0, max_side / max(w, h))
    return max(mult, round(w * scale / mult) * mult), max(mult, round(h * scale / mult) * mult)


# ----------------------------------------------------------------------------
# Texto con IA (chat y mejora de prompts)
# ----------------------------------------------------------------------------
def ask_text(messages: list[dict[str, str]], timeout: int = REQUEST_TIMEOUT) -> str:
    """Prioriza Ollama local (ML); si no está disponible, prueba los servicios en línea."""
    errors: list[str] = []

    # Ollama no requiere clave y permite usar el modelo local Qwen si está instalado.
    try:
        response = requests.post(
            f"{OLLAMA_BASE.rstrip('/')}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            headers=HEADERS,
            timeout=min(timeout, 90),
        )
        response.raise_for_status()
        local_text = response.json().get("message", {}).get("content", "").strip()
        if local_text:
            return local_text
        errors.append("Ollama devolvió una respuesta vacía")
    except (requests.RequestException, ValueError) as exc:
        errors.append(f"Ollama local: {exc}")

    key = os.environ.get("POLLINATIONS_API_KEY")
    attempts = (["gen"] if key else []) + ["legacy"]
    for mode in attempts:
        try:
            if mode == "gen":
                prompt = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)[-6000:]
                response = requests.get(GEN_BASE + "/text/" + urllib.parse.quote(prompt, safe=""),
                                        params={"key": key}, headers=HEADERS, timeout=timeout)
            else:
                response = requests.post(TEXT_ENDPOINT, json={"model": "openai", "messages": messages,
                                                              "seed": random.randint(1, 10**6)},
                                         headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            text = response.text.strip()
            if text:
                return text
            errors.append("servicio en línea: respuesta vacía")
        except requests.RequestException as exc:
            errors.append(f"servicio en línea: {exc}")
    raise RuntimeError("; ".join(errors) or "sin respuesta")


# ----------------------------------------------------------------------------
# Búsqueda web para el chat (DuckDuckGo)
# ----------------------------------------------------------------------------
class SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = attributes.get("class", "") or ""
        if tag == "a" and "result__a" in classes:
            self._active = {"title": "", "url": attributes.get("href", "") or "", "snippet": ""}
            self._capture = "title"
            self._buffer = []
        elif self._active is not None and tag in {"a", "div", "td"} and "result__snippet" in classes:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._active is not None and self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._active is None or self._capture is None:
            return
        if self._capture == "title" and tag == "a":
            self._active["title"] = " ".join("".join(self._buffer).split())
            self._capture = None
            if self._active["title"] and self._active["url"]:
                self.results.append(self._active)
        elif self._capture == "snippet" and tag in {"a", "div", "td"}:
            snippet = " ".join("".join(self._buffer).split())
            if snippet:
                self._active["snippet"] = snippet
            self._capture = None


def resolve_ddg_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    target = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("uddg")
    return urllib.parse.unquote(target[0]) if target else url


def _google_credentials() -> tuple[str, str]:
    """Lee las credenciales de Google sin guardarlas dentro del código."""
    key = os.environ.get("GOOGLE_CSE_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    cx = os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_CX", "")
    return key.strip(), cx.strip()


def search_google(query: str, limit: int = 5, image_search: bool = False) -> list[dict[str, str]]:
    """Búsqueda oficial de Google Custom Search JSON API (requiere key y cx)."""
    key, cx = _google_credentials()
    if not key or not cx:
        raise RuntimeError("Faltan GOOGLE_CSE_API_KEY y/o GOOGLE_CSE_ID")
    params: dict[str, Any] = {"key": key, "cx": cx, "q": query, "num": max(1, min(10, limit)), "safe": "active"}
    if image_search:
        params["searchType"] = "image"
    response = requests.get("https://www.googleapis.com/customsearch/v1", params=params,
                            headers=HEADERS, timeout=REQUEST_TIMEOUT)
    if response.status_code in (400, 401, 403, 429):
        detail = ""
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise RuntimeError(f"Google Custom Search API ({response.status_code}): {detail or response.text[:180]}")
    response.raise_for_status()
    out: list[dict[str, str]] = []
    for item in response.json().get("items", []):
        link = item.get("link", "")
        if not link:
            continue
        image = item.get("image", {})
        out.append({"title": re.sub(r"<[^>]+>", "", item.get("title", "Sin título")),
                    "url": link,
                    "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")),
                    "thumb_url": image.get("thumbnailLink", ""),
                    "context_url": image.get("contextLink", "")})
    return out


def search_web(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Usa Google oficial si está configurado; mantiene DuckDuckGo como respaldo."""
    key, cx = _google_credentials()
    google_error = ""
    if key and cx:
        try:
            return search_google(query, limit)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            google_error = str(exc)
    try:
        response = requests.get(SEARCH_ENDPOINT, params={"q": query},
                                headers={"User-Agent": "Mozilla/5.0 (compatible; ELIN/3.0)"}, timeout=15)
        response.raise_for_status()
        parser = SearchResultParser()
        parser.feed(response.text)
        unique: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in parser.results:
            url = resolve_ddg_url(item["url"])
            if url and url not in seen:
                seen.add(url)
                unique.append({**item, "url": url, "source": "DuckDuckGo (respaldo de Google)"})
            if len(unique) >= limit:
                break
        if unique:
            return unique
    except (requests.RequestException, ValueError):
        pass
    # La búsqueda no debe impedir que Ollama responda si ambas fuentes fallan.
    return []


def search_audio(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Busca archivos de audio existentes en Wikimedia Commons y conserva sus créditos."""
    response = requests.get("https://commons.wikimedia.org/w/api.php", headers=HEADERS, timeout=20, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:audio", "gsrnamespace": 6, "gsrlimit": max(1, min(10, limit)),
        "prop": "imageinfo", "iiprop": "url|extmetadata"})
    response.raise_for_status()
    audio_ext = re.compile(r"\.(ogg|oga|opus|mp3|wav|flac|mid|midi|webm|m4a)(?:$|[?#])", re.I)
    out: list[dict[str, str]] = []
    pages = response.json().get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url", "")
        if not url or not audio_ext.search(url):
            continue
        meta = info.get("extmetadata", {})
        creator = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "Desconocido")).strip() or "Desconocido"
        license_name = re.sub(r"<[^>]+>", "", meta.get("LicenseShortName", {}).get("value", "Licencia no indicada")).strip()
        out.append({"title": re.sub(r"^File:", "", page.get("title", "Audio sin título")),
                    "url": url, "page_url": info.get("descriptionurl", url),
                    "creator": creator, "license": license_name})
        if len(out) >= limit:
            break
    return out


def search_google_images(query: str, limit: int = 8) -> list[SearchResult]:
    """Convierte resultados de imágenes de Google a las tarjetas visuales existentes."""
    items = search_google(query, limit, image_search=True)
    return [SearchResult(it["title"] or "Imagen de Google", it.get("thumb_url") or it["url"], it["url"],
                         it.get("context_url") or it["url"], "Consultar página de origen", "Revisar licencia en origen", "Google")
            for it in items if it.get("url")]


# ----------------------------------------------------------------------------
# Motores de creación de imágenes
# ----------------------------------------------------------------------------
Notify = Callable[[str], None]


def _image_from_response(response: requests.Response) -> Image.Image:
    response.raise_for_status()
    if "image" not in response.headers.get("Content-Type", "image"):
        raise RuntimeError("el servicio no devolvió una imagen")
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def gen_pollinations(prompt: str, w: int, h: int, notify: Notify, model: str) -> Image.Image:
    key = os.environ.get("POLLINATIONS_API_KEY")
    params = {"model": model, "width": w, "height": h, "seed": random.randint(1, 10**6), "nologo": "true"}
    headers = dict(HEADERS)
    if key:
        url = GEN_BASE + "/image/" + urllib.parse.quote(prompt, safe="")
        headers["Authorization"] = f"Bearer {key}"
    else:
        url = IMAGE_ENDPOINT + urllib.parse.quote(prompt, safe="")
    return _image_from_response(requests.get(url, params=params, headers=headers, timeout=(10, 90)))


def gen_flux(prompt: str, w: int, h: int, notify: Notify) -> Image.Image:
    return gen_pollinations(prompt, w, h, notify, "flux")


def gen_turbo(prompt: str, w: int, h: int, notify: Notify) -> Image.Image:
    return gen_pollinations(prompt, w, h, notify, ALT_POLLINATIONS_MODEL)


def gen_horde(prompt: str, w: int, h: int, notify: Notify) -> Image.Image:
    """Stable Horde: red comunitaria y gratuita de GPUs (clave anónima, cola lenta)."""
    headers = {**HEADERS, "apikey": os.environ.get("HORDE_API_KEY", "0000000000"), "Client-Agent": "ELIN:3.0:anon"}
    hw, hh = fit_size(w, h, 576, 64)
    payload = {"prompt": prompt, "nsfw": False, "censor_nsfw": True, "r2": True, "slow_workers": True,
               "params": {"width": hw, "height": hh, "steps": 25, "n": 1, "cfg_scale": 7, "sampler_name": "k_euler_a"}}
    response = requests.post(HORDE_BASE + "/generate/async", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    job_id = response.json()["id"]
    deadline = time.time() + 150
    while time.time() < deadline:
        check = requests.get(f"{HORDE_BASE}/generate/check/{job_id}", headers=headers, timeout=20).json()
        if check.get("faulted"):
            raise RuntimeError("Stable Horde reportó un fallo")
        if check.get("done"):
            break
        notify(f"Stable Horde · cola {check.get('queue_position', '?')} · ~{check.get('wait_time', '?')} s")
        time.sleep(3)
    else:
        try:
            requests.delete(f"{HORDE_BASE}/generate/status/{job_id}", headers=headers, timeout=10)
        except requests.RequestException:
            pass
        raise TimeoutError("Stable Horde tardó demasiado")
    status = requests.get(f"{HORDE_BASE}/generate/status/{job_id}", headers=headers, timeout=30).json()
    img = status["generations"][0]["img"]
    if img.startswith("http"):
        data = requests.get(img, headers=HEADERS, timeout=40).content
    else:
        data = base64.b64decode(img)
    return Image.open(io.BytesIO(data)).convert("RGB")


def gen_hf(prompt: str, w: int, h: int, notify: Notify) -> Image.Image:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("falta HF_TOKEN")
    hw, hh = fit_size(w, h, 1024, 8)
    response = requests.post(HF_BASE + HF_MODEL, headers={**HEADERS, "Authorization": f"Bearer {token}"},
                             json={"inputs": prompt, "parameters": {"width": hw, "height": hh}}, timeout=(10, 120))
    return _image_from_response(response)


_local_pipeline: Any = None
_local_lock = threading.Lock()


def gen_local(prompt: str, w: int, h: int, notify: Notify) -> Image.Image:
    """Stable Diffusion Turbo con PyTorch + diffusers, en tu propio equipo."""
    global _local_pipeline
    import torch
    from diffusers import AutoPipelineForText2Image

    with _local_lock:
        if _local_pipeline is None:
            if torch.cuda.is_available():
                device, dtype = "cuda", torch.float16
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device, dtype = "mps", torch.float32
            else:
                device, dtype = "cpu", torch.float32
            notify("Cargando modelo local…")
            try:
                pipe = AutoPipelineForText2Image.from_pretrained(LOCAL_MODEL, torch_dtype=dtype, local_files_only=True)
            except Exception:
                notify("Descargando modelo local (solo la primera vez)…")
                pipe = AutoPipelineForText2Image.from_pretrained(LOCAL_MODEL, torch_dtype=dtype)
            pipe.set_progress_bar_config(disable=True)
            _local_pipeline = pipe.to(device)
    notify("Generando con IA local…")
    lw, lh = fit_size(w, h, 512, 8)
    generator = torch.Generator(device="cpu").manual_seed(random.randint(1, 10**6))
    result = _local_pipeline(prompt=prompt, num_inference_steps=4, guidance_scale=0.0, width=lw, height=lh, generator=generator)
    return result.images[0].convert("RGB")


def gen_procedural(prompt: str, w: int, h: int, notify: Notify) -> Image.Image:
    """Último recurso: arte generativo con Pillow (no es aprendizaje automático)."""
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed ^ random.getrandbits(32))
    hue = rng.uniform(0.0, 0.14)

    def col(hh: float, s: float, v: float) -> tuple[int, int, int]:
        r, g, b = colorsys.hsv_to_rgb(hh % 1.0, s, v)
        return int(r * 255), int(g * 255), int(b * 255)

    top, bottom = col(hue + 0.86, 0.6, 0.30), col(hue, 0.7, 1.0)
    image = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(image)
    for y in range(h):
        t = (y / h) ** 1.3
        draw.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    m = min(w, h)
    sun_x, sun_y, sun_r = rng.randint(w // 4, w * 3 // 4), int(h * 0.52), int(m * rng.uniform(0.11, 0.17))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([sun_x - sun_r * 2, sun_y - sun_r * 2, sun_x + sun_r * 2, sun_y + sun_r * 2], fill=col(hue + 0.04, 0.6, 1.0) + (170,))
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(m // 12)))
    draw = ImageDraw.Draw(image)
    draw.ellipse([sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r], fill=col(hue + 0.05, 0.2, 1.0) + (255,))
    for _ in range(140):
        x, y, r = rng.randint(0, w), rng.randint(0, int(h * 0.5)), rng.choice((1, 1, 2))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=col(hue + 0.08, 0.2, 1.0) + (rng.randint(80, 220),))
    for layer in range(6):
        base = h * (0.56 + 0.075 * layer)
        amp, freq, phase = rng.uniform(10, 42), rng.uniform(1.0, 3.5), rng.uniform(0, math.tau)
        pts = [(x, base + amp * math.sin(x / w * freq * math.tau + phase) + amp * 0.5 * math.sin(x / w * freq * 5 + phase * 2))
               for x in range(0, w + 1, 6)]
        draw.polygon(pts + [(w, h), (0, h)], fill=col(hue + 0.9 + 0.01 * layer, 0.7, max(0.08, 0.46 - 0.065 * layer)) + (255,))
    return image.convert("RGB")


PROVIDER_FUNCS: dict[str, Callable[[str, int, int, Notify], Image.Image]] = {
    "flux": gen_flux, "turbo": gen_turbo, "horde": gen_horde, "hf": gen_hf, "local": gen_local, "procedural": gen_procedural,
}
ONLINE_PROVIDERS = {"flux", "turbo", "horde", "hf"}
AUTO_ORDER = ["flux", "turbo", "hf", "horde", "local", "procedural"]


def provider_available(key: str) -> bool:
    if key == "hf":
        return bool(os.environ.get("HF_TOKEN"))
    if key == "local":
        return importlib.util.find_spec("torch") is not None and importlib.util.find_spec("diffusers") is not None
    return True


# ----------------------------------------------------------------------------
# Búsqueda de imágenes (varias fuentes)
# ----------------------------------------------------------------------------
def search_openverse(query: str, n: int = 18) -> list[SearchResult]:
    r = requests.get("https://api.openverse.org/v1/images/", params={"q": query, "page_size": n, "mature": "false"},
                     headers=HEADERS, timeout=15)
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []):
        thumb = it.get("thumbnail") or it.get("url")
        if not thumb:
            continue
        lic = (it.get("license") or "").upper()
        ver = it.get("license_version") or ""
        out.append(SearchResult(it.get("title") or "Sin título", thumb, it.get("url") or thumb,
                                it.get("foreign_landing_url") or it.get("url") or "", it.get("creator") or "Desconocido",
                                f"CC {lic} {ver}".strip() if lic else "Licencia abierta", "Openverse"))
    return out


def search_wikimedia(query: str, n: int = 18) -> list[SearchResult]:
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=HEADERS, timeout=15, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
        "gsrlimit": n, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 640})
    r.raise_for_status()
    out = []
    for page in (r.json().get("query", {}).get("pages", {})).values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url", "")
        if not info.get("thumburl") or not re.search(r"\.(jpe?g|png|webp|gif)$", url, re.I):
            continue
        meta = info.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip() or "Desconocido"
        lic = meta.get("LicenseShortName", {}).get("value", "Licencia abierta")
        title = re.sub(r"^File:|\.\w+$", "", page.get("title", "Sin título"))
        out.append(SearchResult(title, info["thumburl"], url, info.get("descriptionurl", url), artist, lic, "Wikimedia"))
    return out


def search_pexels(query: str, n: int = 18) -> list[SearchResult]:
    r = requests.get("https://api.pexels.com/v1/search", params={"query": query, "per_page": n},
                     headers={**HEADERS, "Authorization": os.environ.get("PEXELS_API_KEY", "")}, timeout=15)
    r.raise_for_status()
    return [SearchResult(p.get("alt") or "Foto de Pexels", p["src"]["medium"], p["src"]["large2x"], p.get("url", ""),
                         p.get("photographer", "Desconocido"), "Licencia Pexels", "Pexels") for p in r.json().get("photos", [])]


def search_unsplash(query: str, n: int = 18) -> list[SearchResult]:
    r = requests.get("https://api.unsplash.com/search/photos", params={"query": query, "per_page": n},
                     headers={**HEADERS, "Authorization": f"Client-ID {os.environ.get('UNSPLASH_ACCESS_KEY', '')}"}, timeout=15)
    r.raise_for_status()
    return [SearchResult(p.get("alt_description") or "Foto de Unsplash", p["urls"]["small"], p["urls"]["full"],
                         p["links"]["html"], p["user"]["name"], "Licencia Unsplash", "Unsplash") for p in r.json().get("results", [])]


# clave, etiqueta, función, variable de entorno requerida
SEARCH_SOURCES: list[tuple[str, str, Callable[[str], list[SearchResult]], str | None]] = [
    ("openverse", "Openverse", search_openverse, None),
    ("wikimedia", "Wikimedia", search_wikimedia, None),
    ("pexels", "Pexels", search_pexels, "PEXELS_API_KEY"),
    ("unsplash", "Unsplash", search_unsplash, "UNSPLASH_ACCESS_KEY"),
]


# ----------------------------------------------------------------------------
# Fondo: color sólido claro con trama de plantas apenas visible
# ----------------------------------------------------------------------------
def build_plant_tile(size: int, bg: tuple[int, int, int], ink: tuple[int, int, int], seed: int = 11) -> Image.Image:
    """Mosaico repetible (sin costuras) de ramitas y hojas dibujadas a línea."""
    ss = 2
    S = size * ss
    rng = random.Random(seed)
    img = Image.new("RGB", (S, S), bg)
    d = ImageDraw.Draw(img)
    lw = ss

    def lens(cx: float, cy: float, ang: float, length: float, width: float) -> list[tuple[float, float]]:
        n = 12
        top = [(t * length, math.sin(math.pi * t ** 0.85) * width / 2) for t in (i / n for i in range(n + 1))]
        pts = top + [(x, -y) for x, y in reversed(top)]
        ca, sa = math.cos(ang), math.sin(ang)
        return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]

    sprigs = [(rng.uniform(0, S), rng.uniform(0, S), rng.uniform(0, math.tau), rng.uniform(0.28, 0.42) * S,
               rng.uniform(-1.1, 1.1), rng.uniform(0.06, 0.09) * S) for _ in range(11)]
    berries = [(rng.uniform(0, S), rng.uniform(0, S), rng.uniform(4, 8) * ss) for _ in range(18)]

    def draw_sprig(ox: float, oy: float, spec: tuple[float, ...]) -> None:
        x, y, ang, length, curve, leaf = spec
        x += ox
        y += oy
        steps = 16
        step = length / steps
        pts = [(x, y)]
        nodes = []
        for i in range(steps):
            a = ang + curve * (i / steps)
            x += math.cos(a) * step
            y += math.sin(a) * step
            pts.append((x, y))
            nodes.append((x, y, a, i / steps))
        d.line(pts, fill=ink, width=lw)
        for i, (nx, ny, na, t) in enumerate(nodes):
            if i % 2 == 1 and t > 0.12:
                size_l = leaf * (1 - 0.45 * t)
                for side in (-1, 1):
                    la = na + side * 0.85
                    poly = lens(nx, ny, la, size_l, size_l * 0.46)
                    d.line(poly + [poly[0]], fill=ink, width=lw)
                    d.line([(nx, ny), (nx + math.cos(la) * size_l * 0.8, ny + math.sin(la) * size_l * 0.8)], fill=ink, width=1)
        tx, ty, ta, _ = nodes[-1]
        poly = lens(tx, ty, ta, leaf * 0.8, leaf * 0.4)
        d.line(poly + [poly[0]], fill=ink, width=lw)

    for ox in (-S, 0, S):
        for oy in (-S, 0, S):
            for spec in sprigs:
                draw_sprig(ox, oy, spec)
            for bx, by, br in berries:
                d.ellipse([bx + ox - br, by + oy - br, bx + ox + br, by + oy + br], outline=ink, width=lw)
    return img.resize((size, size), Image.Resampling.LANCZOS)


# ----------------------------------------------------------------------------
# Aplicación
# ----------------------------------------------------------------------------
class ElinApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("ELIN | Asistente creativo")
        # Abrir dentro del área visible del escritorio, con tamaño adaptable.
        info = pygame.display.Info()
        desktop_w = max(640, int(getattr(info, "current_w", 0) or WINDOW_WIDTH))
        desktop_h = max(480, int(getattr(info, "current_h", 0) or WINDOW_HEIGHT))
        start_w = min(WINDOW_WIDTH, int(desktop_w * 0.90))
        start_h = min(WINDOW_HEIGHT, int(desktop_h * 0.86))
        self.min_width = min(MIN_WIDTH, max(640, int(desktop_w * 0.80)))
        self.min_height = min(MIN_HEIGHT, max(480, int(desktop_h * 0.72)))
        self.screen = pygame.display.set_mode((start_w, start_h), pygame.RESIZABLE)
        pygame.key.set_repeat(380, 32)
        self._sdl_win: Any = None
        self._set_min_size()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass
        self.clock = pygame.time.Clock()
        self.fonts = {
            "small": pygame.font.SysFont(FONT_BODY, 13),
            "body": pygame.font.SysFont(FONT_BODY, 17),
            "bold": pygame.font.SysFont(FONT_BODY, 15, bold=True),
            "medium": pygame.font.SysFont(FONT_DISPLAY, 19, bold=True),
            "title": pygame.font.SysFont(FONT_DISPLAY, 24, bold=True),
            "brand": pygame.font.SysFont(FONT_DISPLAY, 28, bold=True),
            "hero": pygame.font.SysFont(FONT_DISPLAY, 42, bold=True),
        }
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

        # Estado general: todo vive en un único "feed" central
        self.view = "chat"            # chat | create | search (decide qué hace el cuadro de texto)
        self.input_text = ""
        self.input_lines: list[str] = [""]
        self.status, self.status_kind = "Listo", "ok"
        self.feed: list[dict[str, Any]] = []
        self.scroll = 0
        self.max_scroll = 0
        self.lightbox: GalleryItem | SearchResult | None = None

        # Chat
        self.use_search = True
        self.busy = False
        self.token = 0
        self.speaking = False
        self.speak_loading = False
        self._audio_buf: io.BytesIO | None = None

        # Crear imagen
        self.provider = "auto"
        self.style = "none"
        self.fmt = "square"
        self.enhancing = False
        self.job_ids = itertools.count(1)
        self.search_ids = itertools.count(1)

        # Buscar imágenes
        self.sources_on = {k: True for k, *_ in SEARCH_SOURCES}
        self.thumb_q: queue.Queue[SearchResult] = queue.Queue()
        for _ in range(6):
            threading.Thread(target=self._thumb_worker, daemon=True).start()

        # UI
        self.buttons: list[tuple[pygame.Rect, Callable[[], None]]] = []
        self.hover_any = False
        self._cursor_hand = False
        self._shadow_cache: dict[tuple, pygame.Surface] = {}
        self._tile_cache: dict[tuple, pygame.Surface] = {}
        self._cover_cache: dict[tuple, pygame.Surface] = {}
        self._fit_cache: dict[tuple, pygame.Surface] = {}
        self._bg: pygame.Surface | None = None
        self._bg_size = (0, 0)
        self._plant: pygame.Surface | None = None
        self.menu: str | None = None            # menú desplegable abierto
        self.menu_anchor = pygame.Rect(0, 0, 0, 0)
        self._tip: tuple[str, pygame.Rect] | None = None
        self._block_hover = False
        self._last_asst: dict[str, Any] | None = None
        self.maximized = False
        self.bg_ready = False
        self.local_ml = False
        self.phase = "intro"           # intro -> fade -> main
        self.intro_t0 = time.time()
        self.progress = 0.0
        self.step_index = 0
        self.step_frames = 0
        self.steps_run: set[int] = set()
        self.dyn_label = ""
        self.splash_last: pygame.Surface | None = None
        self.fade_t0 = 0.0
        self.load_steps: list[tuple[str, Callable[[], str | None]]] = [
            ("Preparando la ventana…", lambda: None),
            ("Dibujando el fondo de hojas…", self._step_background),
            ("Comprobando los servicios de IA…", self._step_services),
            ("Buscando el modelo local de aprendizaje automático…", self._step_local),
            ("Preparando botones e iconos…", self._step_icons),
            ("¡Todo listo!", lambda: None),
        ]
        self.running = True
        self._reset_chat()
        self._update_layout()

    # ------------------------------------------------------------------ estado
    @staticmethod
    def _now() -> str:
        return time.strftime("%H:%M")

    def _set_status(self, text: str, kind: str = "ok") -> None:
        self.status, self.status_kind = text, kind

    def _reset_chat(self) -> None:
        welcome = Message("assistant", "¡Hola! Soy ELIN, tu guía. Escríbeme una pregunta, pídeme una imagen o busca fotos: todo aparece aquí mismo. Prueba también ‘buscar audio: lluvia’ o ‘generar audio: Hola, este es mi audio’.", self._now(), meta=True)
        self.feed = [{"kind": "msg", "msg": welcome}]
        self.last_answer = welcome.text
        self.scroll = 0

    def _add_msg(self, role: str, text: str, meta: bool = False, origin: str = "") -> None:
        self.feed.append({"kind": "msg", "msg": Message(role, text, self._now(), meta=meta, origin=origin)})
        self.scroll = 10**7

    # ----------------------------------------------------------------- layout
    def _composer_side_w(self) -> int:
        """Ancho reservado a la derecha del cuadro de texto (botones)."""
        return 62 + (112 if self.view == "create" else 0)

    def _update_layout(self) -> None:
        self.screen = pygame.display.get_surface() or self.screen
        width, height = self.screen.get_size()
        self.width, self.height = width, height
        if self.bg_ready and self._bg_size != (width, height):
            self._build_background(width, height)
        self.cw = min(COL_MAX, width - 48)
        self.x0 = (width - self.cw) // 2
        self.input_lines = wrap_input(self.input_text, self.fonts["body"], max(120, self.cw - 22 - self._composer_side_w()))
        rows = min(5, len(self.input_lines))
        comp_h = rows * 24 + 32
        self.composer_rect = pygame.Rect(self.x0, height - 16 - comp_h, self.cw, comp_h)
        self.strip_rect = pygame.Rect(self.x0, self.composer_rect.y - 8 - 36, self.cw, 36)
        self.feed_rect = pygame.Rect(0, HEADER_H, width, max(60, self.strip_rect.y - 8 - HEADER_H))

    def _build_background(self, width: int, height: int) -> None:
        if self._plant is None:
            tile = build_plant_tile(520, C["bg"], PLANT_INK)
            self._plant = pygame.image.fromstring(tile.tobytes(), tile.size, "RGB")
        surf = pygame.Surface((width, height))
        ts = self._plant.get_width()
        for y in range(0, height, ts):
            for x in range(0, width, ts):
                surf.blit(self._plant, (x, y))
        self._bg, self._bg_size = surf, (width, height)

    # --------------------------------------------------------------- dibujo base
    def _text(self, text: str, font: pygame.font.Font, color: tuple[int, int, int], pos: tuple[int, int]) -> None:
        self.screen.blit(font.render(text, True, color), pos)

    def _center_text(self, text: str, font: pygame.font.Font, color: tuple[int, int, int], cx: int, y: int) -> None:
        surf = font.render(text, True, color)
        self.screen.blit(surf, (cx - surf.get_width() // 2, y))

    def _rounded(self, rect: pygame.Rect, color: tuple[int, int, int], radius: int = 14, border: tuple[int, int, int] | None = None) -> None:
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.screen, border, rect, width=1, border_radius=radius)

    def _shadow(self, rect: pygame.Rect, radius: int = 14, spread: int = 10, alpha: int = 30) -> None:
        key = (rect.w, rect.h, radius, spread, alpha)
        surf = self._shadow_cache.get(key)
        if surf is None:
            surf = pygame.Surface((rect.w + spread * 2, rect.h + spread * 2), pygame.SRCALPHA)
            for i in range(spread, 0, -1):
                a = int(alpha * (1 - i / spread) ** 2)
                pygame.draw.rect(surf, (60, 40, 20, a), pygame.Rect(spread - i, spread - i, rect.w + 2 * i, rect.h + 2 * i), border_radius=radius + i)
            if len(self._shadow_cache) > 120:
                self._shadow_cache.clear()
            self._shadow_cache[key] = surf
        self.screen.blit(surf, (rect.x - spread, rect.y - spread + 3))

    def _tile(self, name: str, size: int, label: str | None = None) -> pygame.Surface:
        key = (name, size, label)
        cached = self._tile_cache.get(key)
        if cached is not None:
            return cached
        k = 3
        big = size * k
        c1, c2 = TILE_COLORS.get(name, TILE_COLORS["default"])
        surf = pygame.Surface((big, big), pygame.SRCALPHA)
        for y in range(big):
            t = y / max(1, big - 1)
            surf.fill(tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,), (0, y, big, 1))
        path = os.path.join(ASSETS_DIR, f"{name}.png")
        loaded = False
        if os.path.exists(path):
            try:
                surf.blit(pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (big, big)), (0, 0))
                loaded = True
            except pygame.error:
                loaded = False
        if not loaded:
            if label:
                font = pygame.font.SysFont(FONT_DISPLAY, int(big * (0.46 if len(label) == 1 else 0.36)), bold=True)
                txt = font.render(label, True, (255, 255, 255))
                surf.blit(txt, txt.get_rect(center=(big // 2, big // 2)))
            else:
                draw_icon(surf, ICON_FOR.get(name, name), big // 2, big // 2, (255, 255, 255), s=int(big * 0.27))
        mask = pygame.Surface((big, big), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=int(big * 0.3))
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        result = pygame.transform.smoothscale(surf, (size, size))
        self._tile_cache[key] = result
        return result

    def _cover(self, surf: pygame.Surface, size: tuple[int, int], radius: int = 10) -> pygame.Surface:
        key = (id(surf), size, radius)
        cached = self._cover_cache.get(key)
        if cached is None:
            sw, sh = surf.get_size()
            scale = max(size[0] / sw, size[1] / sh)
            nw, nh = max(size[0], int(sw * scale + 0.5)), max(size[1], int(sh * scale + 0.5))
            scaled = pygame.transform.smoothscale(surf, (nw, nh))
            cached = pygame.Surface(size, pygame.SRCALPHA)
            cached.blit(scaled, (0, 0), area=pygame.Rect((nw - size[0]) // 2, (nh - size[1]) // 2, size[0], size[1]))
            mask = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
            cached.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            if len(self._cover_cache) > 300:
                self._cover_cache.clear()
            self._cover_cache[key] = cached
        return cached

    def _fitted(self, surf: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        key = (id(surf), size)
        cached = self._fit_cache.get(key)
        if cached is None:
            sw, sh = surf.get_size()
            scale = min(size[0] / sw, size[1] / sh)
            cached = pygame.transform.smoothscale(surf, (max(1, int(sw * scale)), max(1, int(sh * scale))))
            if len(self._fit_cache) > 40:
                self._fit_cache.clear()
            self._fit_cache[key] = cached
        return cached

    def _spinner(self, center: tuple[int, int], radius: int = 14) -> None:
        now = time.time()
        rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        rect.center = center
        pygame.draw.circle(self.screen, C["border"], center, radius, 3)
        pygame.draw.arc(self.screen, C["accent"], rect, now * 4, now * 4 + 2.2, 3)

    def _btn(
        self,
        rect: pygame.Rect,
        action: Callable[[], None],
        label: str = "",
        icon: str | None = None,
        tile: tuple[str, str | None] | None = None,
        style: str = "ghost",
        active: bool = False,
        enabled: bool = True,
        dim: bool = False,
        clip: pygame.Rect | None = None,
        radius: int = 12,
        tile_size: int | None = None,
        tip: str = "",
        trail: str | None = None,
        inset_right: int = 0,
    ) -> bool:
        mouse = pygame.mouse.get_pos()
        hover = (enabled and not self._block_hover and rect.collidepoint(mouse)
                 and (clip is None or clip.collidepoint(mouse)))
        font = self.fonts["bold"]
        fill: tuple[int, int, int] | None
        border: tuple[int, int, int] | None
        if not enabled:
            fill, fg, border = (None if style == "flat" else C["soft"]), C["off"], None
        elif style == "primary":
            fill, fg, border = (C["accent_hover"] if hover else C["accent"]), C["on_accent"], None
            self._shadow(rect, radius, 8, 40 if hover else 26)
        elif style == "flat":
            fill, fg, border = (C["soft"] if hover else None), (C["text"] if hover else C["muted"]), None
        elif style == "chip":
            if active:
                fill, fg, border = C["accent_soft"], C["accent"], C["accent"]
            else:
                fill, fg, border = (C["soft"] if hover else C["panel"]), (C["muted"] if dim else C["text"]), C["border"]
        else:  # ghost
            fill, fg, border = (C["soft"] if hover else C["panel"]), C["text"], C["border"]
        if style == "chip" and active and enabled:
            self._shadow(rect, radius, 8, 18)
        if fill is not None:
            self._rounded(rect, fill, radius, border)
        label_surface = font.render(label, True, fg) if label else None
        lw = label_surface.get_width() if label_surface else 0
        t_size = 0
        if tile:
            t_size = tile_size or (22 if style == "chip" else min(rect.h - 14, 26))
        icon_w = t_size or (18 if icon else 0)
        gap = 9 if (icon_w and label_surface) else 0
        trail_w = 22 if trail else 0
        content_w = icon_w + gap + lw + trail_w
        x = rect.x + (rect.w - inset_right - content_w) // 2
        if tile:
            tsurf = self._tile(tile[0], t_size, tile[1])
            if not enabled or dim:
                tsurf = tsurf.copy()
                tsurf.set_alpha(110)
            self.screen.blit(tsurf, (x, rect.centery - t_size // 2))
            x += t_size + gap
        elif icon:
            draw_icon(self.screen, icon, x + 9, rect.centery, fg, s=8)
            x += 18 + gap
        if label_surface:
            self.screen.blit(label_surface, (x, rect.centery - label_surface.get_height() // 2))
            x += lw
        if trail:
            draw_icon(self.screen, trail, x + 13, rect.centery + 1, fg, s=6)
        if enabled:
            self.buttons.append((rect.clip(clip) if clip else rect, action))
        if hover:
            self.hover_any = True
            if tip:
                self._tip = (tip, rect)
        return hover

    def _origin_pill(self, kind: str, detail: str, x: int, y: int, max_w: int) -> int:
        fill, fg = ORIGIN_COLORS[kind]
        font = self.fonts["small"]
        label = ORIGIN_BADGE[kind]
        w = font.size(label)[0] + 18
        self._rounded(pygame.Rect(x, y, w, 22), fill, 11)
        self.screen.blit(font.render(label, True, fg), (x + 9, y + 3))
        if detail:
            self._text(fit_text(detail, font, max(20, max_w - w - 10)), font, C["muted"], (x + w + 10, y + 4))
        return w

    # ---------------------------------------------------------- cabecera central
    def _draw_top(self) -> None:
        bar = pygame.Rect(0, 0, self.width, HEADER_H)
        pygame.draw.rect(self.screen, C["panel"], bar)
        pygame.draw.line(self.screen, C["border"], (0, HEADER_H - 1), (self.width, HEADER_H - 1))
        cy, cx = HEADER_H // 2, self.width // 2
        font = self.fonts["bold"]
        mouse = pygame.mouse.get_pos()
        modes = [("chat", "Conversar", "chat", "Conversar con ELIN"),
                 ("create", "Crear", "image", "Crear una imagen con IA"),
                 ("search", "Buscar", "search", "Buscar imágenes en internet")]
        full_w = [18 + 8 + font.size(lb)[0] + 28 for _v, lb, _i, _t in modes]
        compact = self.cw < 2 * (204 + sum(full_w) // 2 + 4)
        widths = [44] * 3 if compact else full_w

        # marca
        self.screen.blit(self._tile("logo", 34, "E"), (self.x0, cy - 17))
        brand = self.fonts["title"].render("ELIN", True, C["text"])
        self.screen.blit(brand, (self.x0 + 44, cy - brand.get_height() // 2))

        # selector de modo (control segmentado)
        box = pygame.Rect(0, 0, sum(widths) + 8, 42)
        box.center = (cx, cy)
        self._rounded(box, C["soft"], 21, C["border"])
        sx = box.x + 4
        for (view, label, icon, tip), w in zip(modes, widths):
            seg = pygame.Rect(sx, box.y + 4, w, 34)
            active = self.view == view
            hover = not self._block_hover and seg.collidepoint(mouse)
            if active:
                self._shadow(seg, 17, 6, 30)
                self._rounded(seg, C["accent"], 17)
                fg = C["on_accent"]
            else:
                if hover:
                    self._rounded(seg, C["border"], 17)
                fg = C["text"] if hover else C["muted"]
            content = 18 + (0 if compact else 8 + font.size(label)[0])
            ix = seg.centerx - content // 2
            draw_icon(self.screen, icon, ix + 9, seg.centery, fg, s=7)
            if not compact:
                txt = font.render(label, True, fg)
                self.screen.blit(txt, (ix + 26, seg.centery - txt.get_height() // 2))
            self.buttons.append((seg, lambda v=view: self._goto(v)))
            if hover:
                self.hover_any = True
                self._tip = (tip, seg)
            sx += w

        # acciones a la derecha: nueva conversación + controles de ventana
        rx = self.x0 + self.cw
        maxb = pygame.Rect(rx - 32, cy - 16, 32, 32)
        self._btn(maxb, self._toggle_maximize, "", icon="restore" if self.maximized else "maximize", style="flat",
                  radius=10, tip="Restaurar" if self.maximized else "Maximizar (F11)")
        minb = pygame.Rect(maxb.x - 4 - 32, cy - 16, 32, 32)
        self._btn(minb, self._minimize, "", icon="minimize", style="flat", radius=10, tip="Minimizar")
        new_w = 42 if compact else 104
        newb = pygame.Rect(minb.x - 12 - new_w, cy - 18, new_w, 36)
        self._btn(newb, self._new_chat, "" if compact else "Nueva", icon="plus", radius=18, tip="Nueva conversación (Ctrl+N)")

    # --------------------------------------------------------------------- feed
    def _search_geom(self) -> tuple[int, int, int, int]:
        cols = 4 if self.cw >= 700 else 3
        gap = 14
        tile = (self.cw - (cols - 1) * gap) // cols
        return cols, gap, tile, tile + 42

    def _entry_height(self, e: dict[str, Any]) -> int:
        kind = e["kind"]
        if kind == "msg":
            m: Message = e["msg"]
            mb = min(700, self.cw - 20)
            if m.cache_key != mb:
                m.lines = wrap_text(clean_markdown(m.text), self.fonts["body"], mb - 38)
                m.cache_key = mb
            return len(m.lines) * 24 + (24 if m.role == "user" else 48)
        if kind == "pending":
            return 238
        if kind == "image":
            it: GalleryItem = e["item"]
            card_w = min(self.cw, 520)
            img_w = card_w - 28
            img_h = int(min(360, img_w * it.pil.size[1] / it.pil.size[0]))
            e["img_h"] = img_h
            if "cap" not in e:
                e["cap"] = wrap_text(it.prompt, self.fonts["small"], card_w - 28)[:2]
            return 64 + img_h + 8 + len(e["cap"]) * 19 + 10 + 34 + 12
        if kind == "search":
            cols, gap, _tile, card_h = self._search_geom()
            n = len(e["results"])
            if n == 0:
                return 44 + (70 if e["waiting"] > 0 else 34)
            return 44 + ((n + cols - 1) // cols) * (card_h + gap)
        return 0

    def _draw_feed(self) -> None:
        fr = self.feed_rect
        old_clip = self.screen.get_clip()
        self.screen.set_clip(fr)
        gap = 16
        heights = [self._entry_height(e) for e in self.feed]
        self._last_asst = next((e for e in reversed(self.feed)
                                if e["kind"] == "msg" and e["msg"].role == "assistant"), None)
        total = 18 + sum(h + gap for h in heights)
        chips = len(self.feed) == 1 and not self.busy
        chip_rects: list[tuple[pygame.Rect, tuple[str, ...]]] = []
        if chips:
            cx, cy = self.x0, total
            for chip in CHIPS:
                w = self.fonts["bold"].size(chip[0])[0] + 56
                if cx + w > self.x0 + self.cw:
                    cx, cy = self.x0, cy + 46
                chip_rects.append((pygame.Rect(cx, cy, w, 36), chip))
                cx += w + 10
            total = cy + 56
        if self.busy:
            total += 62
        self.max_scroll = max(0, total - fr.height)
        self.scroll = max(0, min(self.max_scroll, self.scroll))
        y = fr.y + 18 - self.scroll
        for e, h in zip(self.feed, heights):
            if y + h >= fr.top and y <= fr.bottom:
                self._draw_entry(e, y, h)
            y += h + gap
        if self.busy:
            r = pygame.Rect(self.x0, y, 88, 44)
            self._shadow(r, 18, 8, 22)
            self._rounded(r, C["panel"], 18, C["border"])
            for i in range(3):
                phase = 0.5 + 0.5 * math.sin(time.time() * 5 - i * 0.9)
                pygame.draw.circle(self.screen, C["accent"], (r.x + 26 + i * 18, r.centery + int(3 - 6 * phase)), 4)
        for rect, chip in chip_rects:
            r = rect.move(0, fr.y - self.scroll)
            if r.bottom >= fr.top and r.top <= fr.bottom:
                self._btn(r, lambda c=chip: self._use_chip(c), chip[0], tile=(chip[3], None), style="chip", clip=fr, radius=18)
        if self.max_scroll > 0:
            track_h = fr.height - 16
            thumb_h = max(36, int(track_h * fr.height / total))
            thumb_y = fr.y + 8 + int((track_h - thumb_h) * self.scroll / self.max_scroll)
            pygame.draw.rect(self.screen, C["border"], pygame.Rect(self.x0 + self.cw + 8, thumb_y, 4, thumb_h), border_radius=2)
            if self.max_scroll - self.scroll > 220:
                self._btn(pygame.Rect(self.width // 2 - 20, fr.bottom - 52, 40, 40), lambda: setattr(self, "scroll", 10**7),
                          "", icon="down", clip=fr, radius=20)
        self.screen.set_clip(old_clip)

    def _draw_entry(self, e: dict[str, Any], y: int, h: int) -> None:
        kind = e["kind"]
        fr = self.feed_rect
        body = self.fonts["body"]
        if kind == "msg":
            m: Message = e["msg"]
            small = self.fonts["small"]
            mb = min(700, self.cw - 20)
            is_user = m.role == "user"
            width = max(160, min(mb, max((body.size(l)[0] for l in m.lines), default=0) + 40))
            if m.origin and not is_user:
                width = min(max(width, 480), max(mb, 200))
            x = self.x0 + self.cw - width if is_user else self.x0
            r = pygame.Rect(x, y, width, h)
            if is_user:
                self._rounded(r, C["accent_soft"], 18, (246, 210, 192))
            else:
                self._shadow(r, 18, 8, 22)
                self._rounded(r, C["panel"], 18, C["border"])
            source_links = re.findall(r"(?m)^(?:Página|Archivo(?: directo)?|Archivo):\s*(https?://\S+)", m.text)
            link_index = 0
            for i, line in enumerate(m.lines):
                line_y = r.y + 12 + i * 24
                is_link_line = bool(re.match(r"^(?:Página|Archivo(?: directo)?|Archivo):\s*https?://", line.strip()))
                if is_link_line and link_index < len(source_links):
                    url = source_links[link_index]
                    link_index += 1
                    self._text(line, body, (48, 105, 190), (r.x + 19, line_y))
                    link_w = min(body.size(line)[0], r.w - 38)
                    link_rect = pygame.Rect(r.x + 17, line_y - 2, link_w + 4, 23).clip(fr)
                    self.buttons.append((link_rect, lambda target=url: webbrowser.open(target)))
                else:
                    self._text(line, body, C["text"], (r.x + 19, line_y))
            if not is_user:
                # pie del mensaje: origen · hora · acciones (solo al pasar el ratón o en la última respuesta)
                fy = r.bottom - 32
                mouse = pygame.mouse.get_pos()
                hovered = r.collidepoint(mouse) and fr.collidepoint(mouse) and not self._block_hover
                show = hovered or (e is self._last_asst and not m.meta)
                stamp = small.render(m.stamp, True, C["muted"])
                right = r.right - 14
                self.screen.blit(stamp, (right - stamp.get_width(), fy + 5))
                right -= stamp.get_width() + 8
                if show:
                    copy_r = pygame.Rect(right - 26, fy, 26, 24)
                    self._btn(copy_r, lambda t=m.text: self._copy_text(t), "", icon="copy", style="flat",
                              clip=fr, radius=8, tip="Copiar")
                    speak_r = pygame.Rect(copy_r.x - 4 - 26, fy, 26, 24)
                    self._btn(speak_r, lambda t=m.text: self._toggle_speak(t), "",
                              icon="stop" if self.speaking else "speaker", style="flat",
                              enabled=not self.speak_loading, clip=fr, radius=8,
                              tip="Detener lectura" if self.speaking else "Leer en voz alta")
                if m.origin:
                    avail = r.w - 19 - 14 - stamp.get_width() - 8 - 66
                    self._text(fit_text(m.origin, small, max(40, avail)), small, C["muted"], (r.x + 19, fy + 5))
        elif kind == "pending":
            job = e["job"]
            r = pygame.Rect(self.x0, y, min(self.cw, 380), h)
            self._shadow(r, 18, 8, 22)
            self._rounded(r, C["panel"], 18, C["border"])
            label = PROVIDER_LABELS.get(job["provider"], "Auto")
            self._text(label, self.fonts["bold"], C["text"], (r.x + 16, r.y + 14))
            if job["provider"] == "auto":
                self._text("Probando motores de IA; te diré cuál la creó", self.fonts["small"], C["muted"], (r.x + 16, r.y + 42))
            else:
                kind, detail = provider_origin(job["provider"])
                self._origin_pill(kind, "", r.x + 16, r.y + 40, r.w - 32)
            area = pygame.Rect(r.x + 16, r.y + 68, r.w - 32, 120)
            self._rounded(area, C["soft"], 12)
            self._spinner(area.center, 16)
            self._text(fit_text(job["status"], self.fonts["small"], r.w - 32), self.fonts["small"], C["muted"], (r.x + 16, area.bottom + 10))
            self._text(fit_text(job["prompt"], self.fonts["small"], r.w - 32), self.fonts["small"], C["off"], (r.x + 16, area.bottom + 28))
        elif kind == "image":
            it: GalleryItem = e["item"]
            card_w = min(self.cw, 520)
            r = pygame.Rect(self.x0, y, card_w, h)
            self._shadow(r, 18, 9, 24)
            self._rounded(r, C["panel"], 18, C["border"])
            self.screen.blit(self._tile(it.used_key, 20, TILE_LETTERS.get(it.used_key, "?")), (r.x + 14, r.y + 11))
            self._text(it.provider_label, self.fonts["bold"], C["text"], (r.x + 42, r.y + 12))
            ns = self.fonts["small"].render(f"{it.pil.size[0]}×{it.pil.size[1]}", True, C["muted"])
            self.screen.blit(ns, (r.right - 14 - ns.get_width(), r.y + 14))
            o_kind, detail = provider_origin(it.used_key)
            self._origin_pill(o_kind, detail, r.x + 14, r.y + 36, card_w - 28)
            img_rect = pygame.Rect(r.x + 14, r.y + 64, card_w - 28, e["img_h"])
            self.screen.blit(self._cover(it.surface, img_rect.size, 12), img_rect)
            self.buttons.append((img_rect.clip(fr), lambda x=it: self._open_lightbox(x)))
            if img_rect.collidepoint(pygame.mouse.get_pos()) and fr.collidepoint(pygame.mouse.get_pos()) and not self._block_hover:
                self.hover_any = True
            cy = img_rect.bottom + 8
            for line in e["cap"]:
                self._text(line, self.fonts["small"], C["muted"], (r.x + 14, cy))
                cy += 19
            by = r.bottom - 46
            self._btn(pygame.Rect(r.x + 14, by, 112, 34), lambda x=it: self._save_item(x), "Guardar", icon="download",
                      style="primary", clip=fr, radius=17)
            self._btn(pygame.Rect(r.x + 134, by, 100, 34), lambda x=it: self._vary_item(x), "Variar", icon="refresh",
                      clip=fr, radius=17)
            self._btn(pygame.Rect(r.right - 14 - 34, by, 34, 34), lambda x=it: self._delete_item(x), "", icon="trash",
                      clip=fr, radius=17, tip="Eliminar")
        elif kind == "search":
            cols, gap, tile, card_h = self._search_geom()
            n = len(e["results"])
            head = f"Resultados para “{fit_text(e['query'], self.fonts['bold'], self.cw - 260)}”"
            self._text(head, self.fonts["medium"], C["text"], (self.x0, y + 2))
            sub = f"{n} imágenes encontradas en internet" + ("  ·  buscando…" if e["waiting"] > 0 else "")
            self._text(sub, self.fonts["small"], C["muted"], (self.x0, y + 26))
            pw = self.fonts["small"].size(ORIGIN_BADGE["search"])[0] + 18
            self._origin_pill("search", "", self.x0 + self.cw - pw, y + 4, pw + 10)
            if n == 0:
                if e["waiting"] > 0:
                    self._spinner((self.x0 + self.cw // 2, y + 74), 16)
                else:
                    self._text("Sin resultados. Prueba con otras palabras o activa más fuentes.", self.fonts["body"], C["muted"], (self.x0, y + 52))
                return
            for i, res in enumerate(e["results"]):
                r_, c_ = divmod(i, cols)
                rect = pygame.Rect(self.x0 + c_ * (tile + gap), y + 44 + r_ * (card_h + gap), tile, card_h)
                if rect.bottom < fr.top or rect.top > fr.bottom:
                    continue
                self._card(rect, res.surface, res.title, f"{res.source} · {res.license}", res.surface is None and not res.failed,
                           res.failed, lambda x=res: self._open_lightbox(x))

    def _card(self, r: pygame.Rect, surface: pygame.Surface | None, caption: str, sub: str, loading: bool, failed: bool,
              action: Callable[[], None]) -> None:
        fr = self.feed_rect
        mouse = pygame.mouse.get_pos()
        hover = r.collidepoint(mouse) and fr.collidepoint(mouse)
        self._shadow(r, 14, 10 if hover else 7, 34 if hover else 22)
        self._rounded(r, C["panel"], 14, C["accent"] if hover else C["border"])
        img = pygame.Rect(r.x + 8, r.y + 8, r.w - 16, r.w - 16)
        if surface is not None:
            self.screen.blit(self._cover(surface, img.size, 10), img)
        else:
            self._rounded(img, C["soft"], 10)
            if loading:
                self._spinner(img.center)
            elif failed:
                draw_icon(self.screen, "image", img.centerx, img.centery, C["off"], s=12)
        self._text(fit_text(caption, self.fonts["bold"], r.w - 20), self.fonts["bold"], C["text"], (r.x + 10, img.bottom + 6))
        self._text(fit_text(sub, self.fonts["small"], r.w - 20), self.fonts["small"], C["muted"], (r.x + 10, img.bottom + 25))
        self.buttons.append((r.clip(fr), action))
        if hover:
            self.hover_any = True

    # ------------------------------------------------------------------ opciones
    def _dropdown_w(self, label: str, tile: bool) -> int:
        return self.fonts["bold"].size(label)[0] + 50 + (31 if tile else 0)

    def _status_dot(self) -> tuple[int, int, int]:
        if self.status_kind == "error":
            return C["danger"]
        if self.status_kind == "working" or self.busy or any(e["kind"] == "pending" for e in self.feed):
            return C["accent"] if int(time.time() * 3) % 2 == 0 else C["accent_hover"]
        return C["ok"]

    def _draw_strip(self) -> None:
        """Fila compacta sobre el cuadro de texto: opciones del modo actual y estado."""
        r = self.strip_rect
        small = self.fonts["small"]
        wide = self.cw >= 780
        x = r.x
        if self.view == "chat":
            label = "Búsqueda web"
            w = self.fonts["bold"].size(label)[0] + 31 + 28 + 42
            rect = pygame.Rect(x, r.y, w, r.h)
            self._btn(rect, self._toggle_search, label, tile=("globe", None), style="chip", active=self.use_search,
                      radius=18, inset_right=42, tip="Permite que ELIN consulte la web al responder")
            sw_r = pygame.Rect(rect.right - 12 - 30, rect.centery - 8, 30, 16)
            self._rounded(sw_r, C["accent"] if self.use_search else C["off"], 8)
            pygame.draw.circle(self.screen, (255, 255, 255), (sw_r.right - 8 if self.use_search else sw_r.x + 8, sw_r.centery), 6)
            x = rect.right + 8
        else:
            if self.view == "create":
                prov = dict(PROVIDER_CHIPS)[self.provider]
                style = next(l for k, l, _ in STYLES if k == self.style)
                fmt = next(l for k, l, _ in FORMATS if k == self.fmt)
                specs = [("provider", f"Motor: {prov}" if wide else prov, (self.provider, TILE_LETTERS[self.provider]), "Motor de IA"),
                         ("style", f"Estilo: {style}" if wide else style, None, "Estilo visual"),
                         ("fmt", f"Formato: {fmt}" if wide else fmt, None, "Formato de la imagen")]
            else:
                n = sum(1 for k, _lb, _f, env in SEARCH_SOURCES if self.sources_on[k] and (env is None or os.environ.get(env)))
                specs = [("sources", f"Fuentes: {n}/{len(SEARCH_SOURCES)}", ("search", None), "Fuentes de imágenes")]
            for kind, label, tile, tip in specs:
                rect = pygame.Rect(x, r.y, self._dropdown_w(label, tile is not None), r.h)
                self._btn(rect, lambda k=kind, rc=rect: self._toggle_menu(k, rc), label, tile=tile, style="chip",
                          active=self.menu == kind, radius=18, trail="down", tip=tip)
                x = rect.right + 8
        avail = r.right - x - 12
        if avail > 90:
            status = fit_text(self.status, small, avail - 16)
            sw = small.size(status)[0]
            sx = r.right - sw
            pygame.draw.circle(self.screen, self._status_dot(), (sx - 12, r.centery), 4)
            self._text(status, small, C["muted"], (sx, r.centery - small.get_height() // 2))

    def _toggle_menu(self, kind: str, anchor: pygame.Rect) -> None:
        if self.menu == kind:
            self.menu = None
        else:
            self.menu, self.menu_anchor = kind, anchor.copy()

    def _close_menu(self) -> None:
        self.menu = None

    def _choose(self, fn: Callable[[], None]) -> None:
        fn()
        self.menu = None

    def _menu_items(self) -> list[dict[str, Any]]:
        if self.menu == "provider":
            return [{"label": label, "tile": (key, TILE_LETTERS[key]), "checked": self.provider == key,
                     "dim": key in ("hf", "local") and not provider_available(key),
                     "action": lambda k=key: self._choose(lambda: self._pick_provider(k))}
                    for key, label in PROVIDER_CHIPS]
        if self.menu == "style":
            return [{"label": label, "checked": self.style == key,
                     "action": lambda k=key: self._choose(lambda: setattr(self, "style", k))}
                    for key, label, _ in STYLES]
        if self.menu == "fmt":
            return [{"label": label, "sub": f"{size[0]}×{size[1]}", "checked": self.fmt == key,
                     "action": lambda k=key: self._choose(lambda: setattr(self, "fmt", k))}
                    for key, label, size in FORMATS]
        if self.menu == "sources":
            items = []
            for key, label, _fn, env in SEARCH_SOURCES:
                ok = env is None or bool(os.environ.get(env))
                items.append({"label": label, "tile": (key, TILE_LETTERS[key]), "checked": self.sources_on[key] and ok,
                              "dim": not ok, "sub": "" if ok else "requiere clave",
                              "action": lambda k=key, e=env, lb=label: self._toggle_source(k, e, lb)})
            return items
        return []

    def _draw_menu(self) -> None:
        if self.menu is None:
            return
        items = self._menu_items()
        if not items:
            self.menu = None
            return
        self._block_hover = False
        bold, small = self.fonts["bold"], self.fonts["small"]
        ih = 38
        need = 0
        for it in items:
            n = bold.size(it["label"])[0] + (34 if it.get("tile") else 0)
            if it.get("sub"):
                n += small.size(it["sub"])[0] + 14
            need = max(need, n)
        w = max(210, need + 64)
        h = len(items) * ih + 12
        a = self.menu_anchor
        x = max(8, min(a.x, self.width - w - 8))
        y = a.top - 8 - h
        if y < HEADER_H + 4:
            y = min(a.bottom + 8, self.height - h - 8)
        panel = pygame.Rect(x, y, w, h)
        # un clic fuera cierra el menú; un clic dentro no hace nada salvo en las filas
        self.buttons.append((pygame.Rect(0, 0, self.width, self.height), self._close_menu))
        self.buttons.append((panel, lambda: None))
        self._shadow(panel, 16, 14, 44)
        self._rounded(panel, C["panel"], 16, C["border"])
        mouse = pygame.mouse.get_pos()
        for i, it in enumerate(items):
            row = pygame.Rect(panel.x + 6, panel.y + 6 + i * ih, panel.w - 12, ih)
            hover = row.collidepoint(mouse)
            checked, dim = bool(it.get("checked")), bool(it.get("dim"))
            if hover:
                self._rounded(row, C["soft"], 10)
                self.hover_any = True
            elif checked:
                self._rounded(row, C["accent_soft"], 10)
            tx = row.x + 12
            if it.get("tile"):
                t = self._tile(it["tile"][0], 24, it["tile"][1])
                if dim:
                    t = t.copy()
                    t.set_alpha(110)
                self.screen.blit(t, (tx, row.centery - 12))
                tx += 34
            color = C["off"] if dim else (C["accent"] if checked else C["text"])
            lab = bold.render(it["label"], True, color)
            self.screen.blit(lab, (tx, row.centery - lab.get_height() // 2))
            right = row.right - 14
            if checked:
                draw_icon(self.screen, "check", right - 6, row.centery, C["accent"], s=7, w=2)
                right -= 24
            if it.get("sub"):
                sb = small.render(it["sub"], True, C["muted"])
                self.screen.blit(sb, (right - sb.get_width(), row.centery - sb.get_height() // 2))
            self.buttons.append((row, it["action"]))

    def _draw_tooltip(self) -> None:
        if not self._tip:
            return
        text, rect = self._tip
        font = self.fonts["small"]
        surf = font.render(text, True, (255, 255, 255))
        w, h = surf.get_width() + 18, surf.get_height() + 10
        x = max(6, min(rect.centerx - w // 2, self.width - w - 6))
        y = rect.bottom + 8
        if y + h > self.height - 6:
            y = rect.top - 8 - h
        self._rounded(pygame.Rect(x, y, w, h), (48, 43, 39), 8)
        self.screen.blit(surf, (x + 9, y + 5))

    # ----------------------------------------------------------------- composer
    def _draw_composer(self) -> None:
        rect = self.composer_rect
        self._shadow(rect, 24, 14, 36)
        self._rounded(rect, C["panel"], 24, C["border"])
        font = self.fonts["body"]
        tx, ty = rect.x + 22, rect.y + 16
        placeholders = {"chat": "Escribe tu mensaje…", "create": "Describe la imagen que imaginas…",
                        "search": "¿Qué imágenes quieres encontrar?"}
        if not self.input_text:
            self._text(placeholders[self.view], font, C["muted"], (tx, ty))
            caret = (tx, ty)
        else:
            shown = self.input_lines[-5:]
            for i, line in enumerate(shown):
                self._text(line, font, C["text"], (tx, ty + i * 24))
            cx = tx + font.size(shown[-1])[0] + (font.size(" ")[0] if self.input_text.endswith(" ") else 0)
            caret = (cx, ty + (len(shown) - 1) * 24)
        if int(time.time() * 2) % 2 == 0:
            pygame.draw.line(self.screen, C["accent"], (caret[0] + 1, caret[1] + 1), (caret[0] + 1, caret[1] + 21), 2)
        can = bool(self.input_text.strip())
        icon = {"chat": "send", "create": "wand", "search": "search"}[self.view]
        tip = {"chat": "Enviar (Enter)", "create": "Crear imagen (Enter)", "search": "Buscar (Enter)"}[self.view]
        send = pygame.Rect(rect.right - 10 - 40, rect.bottom - 8 - 40, 40, 40)
        self._btn(send, self._submit, "", icon=icon, style="primary", enabled=can, radius=20, tip=tip)
        if self.view == "create":
            enh = pygame.Rect(send.x - 8 - 104, send.y, 104, 40)
            self._btn(enh, self._enhance_prompt, "Mejorar" if not self.enhancing else "…", tile=("wand", None),
                      enabled=can and not self.enhancing, radius=20, tip="Reescribe tu idea como un prompt detallado")

    # ------------------------------------------------------------------ lightbox
    def _draw_lightbox(self) -> None:
        obj = self.lightbox
        if obj is None:
            return
        self.buttons = []
        self.hover_any = False
        shade = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        shade.fill((38, 32, 26, 150))
        self.screen.blit(shade, (0, 0))
        panel = pygame.Rect(0, 0, min(self.width - 80, 1000), min(self.height - 50, 740))
        panel.center = (self.width // 2, self.height // 2)
        self.buttons.append((pygame.Rect(0, 0, self.width, self.height), self._close_lightbox))
        self.buttons.append((panel, lambda: None))
        self._shadow(panel, 24, 18, 50)
        self._rounded(panel, C["panel"], 24, C["border"])
        loading = False
        if isinstance(obj, GalleryItem):
            surface, title = obj.surface, obj.prompt
            meta, extra = f"{obj.provider_label} · {obj.size[0]}×{obj.size[1]}", ""
        else:
            surface = obj.full_surface or obj.surface
            title, meta, extra = obj.title, f"{obj.source} · {obj.license}", f"Autor: {obj.creator}"
            loading = obj.full_surface is None and obj.full_loading
        area = pygame.Rect(panel.x + 20, panel.y + 20, panel.w - 40, panel.h - 40 - 160)
        self._rounded(area, C["soft"], 16)
        if surface is not None:
            fitted = self._fitted(surface, (area.w - 8, area.h - 8))
            self.screen.blit(fitted, fitted.get_rect(center=area.center))
        if loading:
            self._text("Cargando versión grande…", self.fonts["small"], C["muted"], (area.x + 14, area.bottom - 24))
        ty = area.bottom + 12
        for line in wrap_text(title, self.fonts["bold"], panel.w - 40)[:2]:
            self._text(line, self.fonts["bold"], C["text"], (panel.x + 22, ty))
            ty += 21
        self._text(fit_text(meta + ("   ·   " + extra if extra else ""), self.fonts["small"], panel.w - 44), self.fonts["small"], C["muted"], (panel.x + 22, ty + 2))
        if isinstance(obj, GalleryItem):
            o_kind, o_detail = provider_origin(obj.used_key)
        else:
            o_kind, o_detail = "search", f"Encontrada en internet · {obj.source}"
        self._origin_pill(o_kind, o_detail, panel.x + 22, ty + 28, panel.w - 44)
        by = panel.bottom - 60
        bx = panel.x + 20
        if isinstance(obj, GalleryItem):
            self._btn(pygame.Rect(bx, by, 140, 42), lambda: self._save_item(obj), "Guardar", icon="download", style="primary", radius=16)
            self._btn(pygame.Rect(bx + 150, by, 120, 42), lambda: (self._close_lightbox(), self._vary_item(obj)), "Variar", icon="refresh", radius=16)
        else:
            self._btn(pygame.Rect(bx, by, 210, 42), lambda: self._save_result(obj), "Guardar con créditos", icon="download", style="primary", radius=16)
            self._btn(pygame.Rect(bx + 220, by, 120, 42), lambda: self._open_result(obj), "Página", icon="link", radius=16)
            self._btn(pygame.Rect(bx + 350, by, 150, 42), lambda: self._similar_result(obj), "Crear similar", icon="wand", radius=16)
        self._btn(pygame.Rect(panel.right - 14 - 36, panel.y + 14, 36, 36), self._close_lightbox, "", icon="close",
                  radius=18, tip="Cerrar (Esc)")

    # ------------------------------------------------------------------ ventana
    def _sdl_window(self) -> Any:
        if self._sdl_win is None:
            try:
                from pygame._sdl2.video import Window
                self._sdl_win = Window.from_display_module()
            except Exception:
                self._sdl_win = False
        return self._sdl_win or None

    def _set_min_size(self) -> None:
        win = self._sdl_window()
        if win is not None:
            try:
                win.minimum_size = (getattr(self, "min_width", MIN_WIDTH),
                                    getattr(self, "min_height", MIN_HEIGHT))
            except Exception:
                pass

    def _minimize(self) -> None:
        try:
            win = self._sdl_window()
            if win is not None:
                win.minimize()
            else:
                pygame.display.iconify()
        except Exception:
            pygame.display.iconify()

    def _toggle_maximize(self) -> None:
        """Pide al sistema operativo maximizar/restaurar sin recrear la pantalla."""
        try:
            win = self._sdl_window()
            if win is None:
                self._set_status("No se pudo acceder al control nativo de ventana. Actualiza pygame.", "error")
                return
            if self.maximized:
                win.restore()
            else:
                win.maximize()
            # El estado se actualiza con WINDOWMAXIMIZED/WINDOWRESTORED.
        except Exception as exc:
            self._set_status(f"No se pudo cambiar el tamaño de la ventana: {exc}", "error")

    # ------------------------------------------------------------- presentación
    def _step_background(self) -> str | None:
        self.bg_ready = True
        width, height = self.screen.get_size()
        self._build_background(width, height)
        return None

    def _step_services(self) -> str | None:
        keys = sum(bool(os.environ.get(k)) for k in
                   ("POLLINATIONS_API_KEY", "HF_TOKEN", "HORDE_API_KEY", "PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY"))
        return f"Servicios de IA listos · claves detectadas: {keys}"

    def _step_local(self) -> str | None:
        self.local_ml = provider_available("local")
        return ("Modelo local (PyTorch + diffusers): disponible" if self.local_ml
                else "Modelo local no instalado: usaré servicios en línea")

    def _step_icons(self) -> str | None:
        for name in ("chat", "create", "search"):
            self._tile(name, 34)
        for name in ("plus", "globe", "copy", "speaker", "stop", "refresh", "trash", "wand", "link", "download"):
            self._tile(name, 26)
        self._tile("logo", 36, "E")
        self._tile("logo", 96, "E")
        for key, letter in TILE_LETTERS.items():
            self._tile(key, 22, letter)
        return None

    def _tick_intro(self) -> None:
        now = time.time()
        total = len(self.load_steps)
        if self.step_index < total:
            if self.step_index not in self.steps_run:
                self.step_frames += 1
                if self.step_frames >= 2:      # deja pintar la etiqueta antes del trabajo pesado
                    self.dyn_label = self.load_steps[self.step_index][1]() or ""
                    self.steps_run.add(self.step_index)
                    self.step_t0 = now
            elif now - self.step_t0 >= STEP_MIN:
                self.step_index += 1
                self.step_frames = 0
                if self.step_index < total:
                    self.dyn_label = ""
        partial = min(1.0, (now - self.step_t0) / STEP_MIN) if self.step_index in self.steps_run else 0.0
        target = min(1.0, (self.step_index + partial) / total)
        self.progress += (target - self.progress) * 0.14
        if self.step_index >= total and self.progress > 0.995 and now - self.intro_t0 >= MIN_INTRO:
            self._start_fade()

    def _skip_intro(self) -> None:
        for i, (_label, fn) in enumerate(self.load_steps):
            if i not in self.steps_run:
                fn()
                self.steps_run.add(i)
        self.step_index = len(self.load_steps)
        self.progress = 1.0
        self._start_fade()

    def _start_fade(self) -> None:
        self.splash_last = self.screen.copy()
        self.phase = "fade"
        self.fade_t0 = time.time()

    def _draw_fade(self) -> None:
        if self.phase != "fade" or self.splash_last is None:
            return
        t = (time.time() - self.fade_t0) / 0.6
        if t >= 1:
            self.phase = "main"
            self.splash_last = None
            return
        overlay = self.splash_last
        if overlay.get_size() != self.screen.get_size():
            overlay = pygame.transform.smoothscale(overlay, self.screen.get_size())
        overlay.set_alpha(int(255 * (1 - t)))
        self.screen.blit(overlay, (0, 0))

    def _draw_intro(self) -> None:
        self.screen = pygame.display.get_surface() or self.screen
        screen = self.screen
        width, height = screen.get_size()
        if self._bg is not None and self._bg_size == (width, height):
            screen.blit(self._bg, (0, 0))
        else:
            screen.fill(C["bg"])
        t = time.time() - self.intro_t0
        cx, cy = width // 2, max(130, height // 2 - 120)

        rings = pygame.Surface((320, 320), pygame.SRCALPHA)
        for i in range(3):
            phase = ((t * 0.5) + i / 3) % 1.0
            pygame.draw.circle(rings, (*C["accent"], int(120 * (1 - phase))), (160, 160), int(54 + phase * 90), 2)
        screen.blit(rings, (cx - 160, cy - 160))
        screen.blit(self._tile("logo", 96, "E"), (cx - 48, cy - 48))

        greeting = "Hola, soy ELIN, tu guía."
        typed = greeting[: int(t * 20)]
        hero = self.fonts["hero"]
        surf = hero.render(typed, True, C["text"])
        screen.blit(surf, (cx - hero.size(greeting)[0] // 2, cy + 78))
        if len(typed) < len(greeting) and int(t * 3) % 2 == 0:
            gx = cx - hero.size(greeting)[0] // 2 + surf.get_width() + 3
            pygame.draw.line(screen, C["accent"], (gx, cy + 84), (gx, cy + 84 + hero.get_height() - 14), 3)

        y = cy + 78 + hero.get_height() + 16
        reveal = (t - len(greeting) / 20 - 0.2) / 0.7
        if reveal > 0:
            alpha = int(255 * min(1.0, reveal))
            lines = [
                ("Te acompaño a conversar, crear imágenes y buscarlas en internet.", C["muted"]),
                ("Uso modelos de aprendizaje automático: Ollama local si está disponible y servicios de IA en línea como respaldo.", C["text"]),
                ("Cada imagen indica si se generó con IA, se buscó en internet o se dibujó con recursos de Python.", C["muted"]),
            ]
            for text, color in lines:
                for sub in wrap_text(text, self.fonts["body"], min(width - 80, 680)):
                    line = self.fonts["body"].render(sub, True, color)
                    line.set_alpha(alpha)
                    screen.blit(line, (cx - line.get_width() // 2, y))
                    y += 24
        bar = pygame.Rect(0, 0, 420, 10)
        bar.center = (cx, y + 34)
        pygame.draw.rect(screen, C["border"], bar, border_radius=5)
        fill = bar.copy()
        fill.width = max(10, int(bar.width * self.progress))
        pygame.draw.rect(screen, C["accent"], fill, border_radius=5)
        label = self.dyn_label or self.load_steps[min(self.step_index, len(self.load_steps) - 1)][0]
        self._text(fit_text(label, self.fonts["small"], 330), self.fonts["small"], C["muted"], (bar.x, bar.bottom + 12))
        pct = self.fonts["small"].render(f"{int(self.progress * 100)}%", True, C["text"])
        screen.blit(pct, (bar.right - pct.get_width(), bar.bottom + 12))
        self._center_text("Pulsa cualquier tecla o haz clic para saltar", self.fonts["small"], C["off"], cx, height - 36)

    def draw(self) -> None:
        if self.phase == "intro":
            self._draw_intro()
            pygame.display.flip()
            return
        self._update_layout()
        self.buttons = []
        self.hover_any = False
        self._tip = None
        self._block_hover = self.menu is not None
        if self._bg is not None:
            self.screen.blit(self._bg, (0, 0))
        else:
            self.screen.fill(C["bg"])
        self._draw_feed()
        self._draw_top()
        self._draw_strip()
        self._draw_composer()
        self._draw_menu()
        self._draw_lightbox()
        self._draw_fade()
        self._draw_tooltip()
        if self.hover_any != self._cursor_hand:
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if self.hover_any else pygame.SYSTEM_CURSOR_ARROW)
            except (pygame.error, AttributeError):
                pass
            self._cursor_hand = self.hover_any
        pygame.display.flip()

    # ------------------------------------------------------------------ acciones
    def _goto(self, view: str) -> None:
        self.view = view
        self.menu = None
        self._set_status({"chat": "Conversación", "create": "Elige un motor y describe tu imagen", "search": "Busca fotos en varias fuentes"}[view])

    def _toggle_search(self) -> None:
        self.use_search = not self.use_search
        self._set_status("Búsqueda web activada en el chat" if self.use_search else "Búsqueda web desactivada")

    def _use_chip(self, chip: tuple[str, ...]) -> None:
        self._goto(chip[1])
        self.input_text = chip[2]

    def _new_chat(self) -> None:
        self.token += 1
        self.busy = False
        self.input_text = ""
        self.lightbox = None
        self._stop_audio()
        self._reset_chat()
        self._goto("chat")
        self._set_status("Nueva conversación iniciada")

    def _submit(self) -> None:
        self.menu = None
        {"chat": self._send_message, "create": self._create_images, "search": self._search_images}[self.view]()

    def _quick_create(self) -> None:
        if self.input_text.strip():
            self._goto("create")
            self._create_images()

    def _copy_text(self, text: str) -> None:
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            if hasattr(pygame.scrap, "put_text"):
                pygame.scrap.put_text(text)
            else:
                pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
            self._set_status("Texto copiado al portapapeles")
        except Exception:
            self._set_status("No se pudo acceder al portapapeles", "error")

    def _paste(self) -> None:
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            if hasattr(pygame.scrap, "get_text"):
                data = pygame.scrap.get_text() or ""
            else:
                raw = pygame.scrap.get(pygame.SCRAP_TEXT)
                data = raw.decode("utf-8", errors="ignore") if raw else ""
            data = data.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
            self.input_text = (self.input_text + data)[:MAX_INPUT]
        except Exception:
            self._set_status("No se pudo pegar desde el portapapeles", "error")

    # -------- chat
    def _send_message(self) -> None:
        prompt = clean_prompt(self.input_text)
        if not prompt:
            return
        if self.busy:
            self._set_status("Espera a que termine la respuesta actual", "error")
            return
        lower_prompt = prompt.lower()
        if lower_prompt.startswith(("buscar audio:", "busca audio:", "audio:")):
            query = prompt.split(":", 1)[1].strip()
            if not query:
                self._set_status("Escribe el tema después de ‘buscar audio:’", "error")
                return
            self.input_text = ""
            self._add_msg("user", prompt)
            self.busy = True
            self._set_status("Buscando audios existentes…", "working")
            threading.Thread(target=self._audio_search_worker, args=(query, self.token), daemon=True).start()
            return
        if lower_prompt.startswith(("generar audio:", "crear audio:", "guardar audio:")):
            text = prompt.split(":", 1)[1].strip()
            if not text:
                self._set_status("Escribe el texto después de ‘generar audio:’", "error")
                return
            self.input_text = ""
            self._add_msg("user", prompt)
            self.busy = True
            self._set_status("Generando y guardando audio MP3…", "working")
            threading.Thread(target=self._audio_generate_worker, args=(text[:4500], self.token), daemon=True).start()
            return
        history = [{"role": e["msg"].role, "content": e["msg"].text[:1500]}
                   for e in self.feed if e["kind"] == "msg" and not e["msg"].meta][-8:]
        self.input_text = ""
        self._add_msg("user", prompt)
        self.busy = True
        self._set_status("Buscando y generando…" if self.use_search else "Generando respuesta…", "working")
        threading.Thread(target=self._text_worker, args=(prompt, history, self.use_search, self.token), daemon=True).start()

    def _text_worker(self, prompt: str, history: list[dict[str, str]], use_search: bool, token: int) -> None:
        try:
            results = search_web(prompt) if use_search else []
            audio_results: list[dict[str, str]] = []
            image_results: list[SearchResult] = []
            if use_search:
                # Los medios son complementarios: si una fuente falla, el chat sigue funcionando.
                try:
                    audio_results = search_audio(prompt, 3)
                except Exception:
                    audio_results = []
                try:
                    key, cx = _google_credentials()
                    image_results = search_google_images(prompt, 6) if key and cx else search_openverse(prompt, 6)
                except Exception:
                    try:
                        image_results = search_openverse(prompt, 6)
                    except Exception:
                        image_results = []
            if results:
                sources = "\n".join(f"[{i}] {it['title']} — {it.get('snippet') or 'Sin descripción disponible.'} ({it['url']}) [Fuente: {it.get('source', 'web')}]"
                                    for i, it in enumerate(results, start=1))
            else:
                sources = "No se obtuvieron resultados web." if use_search else "Búsqueda web desactivada por el usuario."
            if audio_results:
                audio_context = "\nAudios existentes encontrados (verifica atribución/licencia antes de reutilizar):\n" + "\n".join(
                    f"- {a['title']} | autor: {a['creator']} | licencia: {a['license']} | página: {a['page_url']} | archivo: {a['url']}"
                    for a in audio_results)
            else:
                audio_context = "\nNo se encontraron audios existentes relacionados en Wikimedia Commons."
            content = f"Contexto de búsqueda web (puede estar incompleto):\n{sources}{audio_context}\n\nSolicitud del usuario:\n{prompt}"
            answer = ask_text([{"role": "system", "content": SYSTEM_INSTRUCTIONS}, *history, {"role": "user", "content": content}])
            if audio_results:
                audio_lines = ["", "Audios relacionados encontrados en Wikimedia Commons:"]
                for a in audio_results:
                    audio_lines.append(f"• {a['title']} | {a['creator']} | {a['license']}")
                    audio_lines.append(f"Página: {a['page_url']}")
                    audio_lines.append(f"Archivo: {a['url']}")
                answer += "\n\n" + "\n".join(audio_lines)
            self.events.put(("text_done", (token, answer)))
            if image_results:
                self.events.put(("related_media", (token, prompt, image_results)))
        except Exception as exc:
            self.events.put(("error", (token, f"No pude completar la solicitud. Comprueba tu conexión e inténtalo de nuevo.\n\nDetalle: {exc}")))

    def _audio_search_worker(self, query: str, token: int) -> None:
        try:
            items = search_audio(query, 8)
            if not items:
                message = f"No encontré audios existentes para ‘{query}’ en Wikimedia Commons. Puedes probar con términos más concretos."
            else:
                lines = [f"Encontré {len(items)} audio(s) relacionado(s) con ‘{query}’. Abre la página de origen para escuchar o descargar y revisar la licencia:"]
                for i, item in enumerate(items, 1):
                    lines.extend([f"{i}. {item['title']}", f"Autor: {item['creator']} · Licencia: {item['license']}",
                                  f"Página: {item['page_url']}", f"Archivo directo: {item['url']}", ""])
                message = "\n".join(lines).strip()
            self.events.put(("audio_search_done", (token, message)))
        except Exception as exc:
            self.events.put(("audio_search_done", (token, f"No pude buscar audios: {exc}")))

    def _audio_generate_worker(self, text: str, token: int) -> None:
        try:
            os.makedirs(AUDIO_DIR, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "_", text.lower())[:32].strip("_") or "audio"
            path = os.path.join(AUDIO_DIR, f"elin_{time.strftime('%Y%m%d_%H%M%S')}_{slug}.mp3")
            gTTS(text=text, lang="es").save(path)
            with open(path, "rb") as fh:
                data = fh.read()
            self.events.put(("audio_generated", (token, path, data)))
        except Exception as exc:
            self.events.put(("audio_task_error", (token, f"No pude generar el MP3. Revisa la conexión y gTTS. Detalle: {exc}")))

    # -------- crear imagen
    def _pick_provider(self, key: str) -> None:
        if key == "hf" and not provider_available("hf"):
            self._set_status("Para Hugging Face define la variable HF_TOKEN", "error")
        elif key == "local" and not provider_available("local"):
            self._set_status("Instala: pip install torch diffusers transformers accelerate", "error")
        else:
            self.provider = key
            self._set_status(f"Motor: {dict(PROVIDER_CHIPS)[key]}")

    def _compose_prompt(self, prompt: str) -> str:
        suffix = next(s for k, _l, s in STYLES if k == self.style)
        return f"{prompt}, {suffix}" if suffix else prompt

    def _create_images(self) -> None:
        prompt = clean_prompt(self.input_text)
        if not prompt:
            self._set_status("Escribe una descripción para crear una imagen", "error")
            return
        self.input_text = ""
        if self.provider == "auto":
            providers = ["auto"]
        elif self.provider == "compare":
            providers = ["flux", "turbo"] + (["hf"] if provider_available("hf") else []) + ["horde"]
        else:
            providers = [self.provider]
        size = next(s for k, _l, s in FORMATS if k == self.fmt)
        self._add_msg("user", f"Crear imagen: {prompt}", meta=True)
        for prov in providers:
            self._launch_job(prompt, self._compose_prompt(prompt), prov, size)
        self._set_status(f"Creando con {len(providers)} motores…" if len(providers) > 1 else "Creando imagen…", "working")

    def _launch_job(self, prompt: str, full_prompt: str, provider: str, size: tuple[int, int]) -> None:
        job = {"id": next(self.job_ids), "provider": provider, "prompt": prompt, "full": full_prompt, "size": size, "status": "En cola…"}
        self.feed.append({"kind": "pending", "job": job})
        self.scroll = 10**7
        threading.Thread(target=self._gen_worker, args=(job,), daemon=True).start()

    def _gen_worker(self, job: dict[str, Any]) -> None:
        jid, size = job["id"], job["size"]

        def notify(text: str) -> None:
            self.events.put(("img_status", (jid, text)))

        try:
            if job["provider"] == "auto":
                image, used = self._run_auto(job["full"], size, notify)
            else:
                notify("Conectando…")
                image = PROVIDER_FUNCS[job["provider"]](job["full"], size[0], size[1], notify)
                used = job["provider"]
            image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            self.events.put(("img_done", (jid, image.copy(), used)))
        except Exception as exc:
            self.events.put(("img_fail", (jid, f"{PROVIDER_LABELS.get(job['provider'], 'Auto')}: {exc}")))

    @staticmethod
    def _run_auto(prompt: str, size: tuple[int, int], notify: Notify) -> tuple[Image.Image, str]:
        offline = FORCE_LOCAL
        for key in AUTO_ORDER:
            if not provider_available(key):
                continue
            if key in ONLINE_PROVIDERS and offline:
                continue
            notify(f"Probando {PROVIDER_LABELS[key]}…")
            try:
                return PROVIDER_FUNCS[key](prompt, size[0], size[1], notify), key
            except requests.ConnectionError:
                offline = True
            except Exception:
                continue
        return gen_procedural(prompt, size[0], size[1], notify), "procedural"

    def _enhance_prompt(self) -> None:
        text = clean_prompt(self.input_text)
        if not text or self.enhancing:
            return
        self.enhancing = True
        self._set_status("Mejorando tu prompt con IA…", "working")

        def work() -> None:
            try:
                out = ask_text([{"role": "system", "content": ENHANCE_INSTRUCTIONS}, {"role": "user", "content": text}], timeout=30)
                self.events.put(("enhance_done", out.strip().strip('"')[:MAX_INPUT]))
            except Exception as exc:
                self.events.put(("enhance_fail", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _save_item(self, item: GalleryItem) -> None:
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "_", item.prompt.lower())[:30].strip("_") or "imagen"
            path = os.path.join(SAVE_DIR, f"{time.strftime('%Y%m%d_%H%M%S')}_{slug}.png")
            item.pil.save(path)
            self._set_status(f"Imagen guardada en {path}")
        except OSError as exc:
            self._set_status(f"No se pudo guardar: {exc}", "error")

    def _vary_item(self, item: GalleryItem) -> None:
        self._launch_job(item.prompt, item.full_prompt, item.request_provider, item.size)
        self._set_status("Creando una variación…", "working")

    def _delete_item(self, item: GalleryItem) -> None:
        self.feed = [e for e in self.feed if e.get("item") is not item]
        if self.lightbox is item:
            self.lightbox = None

    # -------- buscar imágenes
    def _toggle_source(self, key: str, env: str | None, label: str) -> None:
        if env and not os.environ.get(env):
            self._set_status(f"Para usar {label} define la variable {env}", "error")
        else:
            self.sources_on[key] = not self.sources_on[key]

    def _search_images(self) -> None:
        query = clean_prompt(self.input_text)
        if not query:
            return
        active = [(k, lb, fn) for k, lb, fn, env in SEARCH_SOURCES if self.sources_on[k] and (env is None or os.environ.get(env))]
        if not active:
            self._set_status("Activa al menos una fuente", "error")
            return
        self.input_text = ""
        sid = next(self.search_ids)
        self._add_msg("user", f"Buscar imágenes: {query}", meta=True)
        self.feed.append({"kind": "search", "sid": sid, "query": query, "results": [], "waiting": len(active)})
        self.scroll = 10**7
        self._set_status("Buscando en varias fuentes…", "working")
        for _k, label, fn in active:
            threading.Thread(target=self._search_worker, args=(sid, label, fn, query), daemon=True).start()

    def _search_worker(self, sid: int, label: str, fn: Callable[[str], list[SearchResult]], query: str) -> None:
        try:
            self.events.put(("search_part", (sid, label, fn(query))))
        except Exception as exc:
            self.events.put(("search_fail", (sid, label, str(exc))))

    def _thumb_worker(self) -> None:
        while True:
            res = self.thumb_q.get()
            try:
                r = requests.get(res.thumb_url, headers=HEADERS, timeout=15)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img.thumbnail((480, 480), Image.Resampling.LANCZOS)
                self.events.put(("thumb", (res, img)))
            except Exception:
                self.events.put(("thumb", (res, None)))

    def _search_entry(self, sid: int) -> dict[str, Any] | None:
        return next((e for e in self.feed if e["kind"] == "search" and e["sid"] == sid), None)

    def _open_lightbox(self, obj: GalleryItem | SearchResult) -> None:
        self.lightbox = obj
        if isinstance(obj, SearchResult) and obj.full_surface is None and not obj.full_loading:
            obj.full_loading = True
            threading.Thread(target=self._full_worker, args=(obj,), daemon=True).start()

    def _close_lightbox(self) -> None:
        self.lightbox = None

    def _full_worker(self, res: SearchResult) -> None:
        try:
            r = requests.get(res.full_url, headers=HEADERS, timeout=30, stream=True)
            r.raise_for_status()
            if int(r.headers.get("Content-Length", "0") or 0) > 12_000_000:
                raise RuntimeError("archivo demasiado grande para la vista previa")
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            self.events.put(("full", (res, img)))
        except Exception:
            self.events.put(("full", (res, None)))

    def _save_result(self, res: SearchResult) -> None:
        self._set_status("Descargando imagen original…", "working")
        threading.Thread(target=self._save_result_worker, args=(res,), daemon=True).start()

    def _save_result_worker(self, res: SearchResult) -> None:
        try:
            r = requests.get(res.full_url, headers=HEADERS, timeout=40)
            r.raise_for_status()
            fmt = (Image.open(io.BytesIO(r.content)).format or "JPEG").lower()
            ext = {"jpeg": "jpg"}.get(fmt, fmt)
            os.makedirs(SAVE_DIR, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "_", res.title.lower())[:30].strip("_") or "foto"
            base = os.path.join(SAVE_DIR, f"{time.strftime('%Y%m%d_%H%M%S')}_{slug}")
            with open(f"{base}.{ext}", "wb") as fh:
                fh.write(r.content)
            with open(f"{base}.txt", "w", encoding="utf-8") as fh:
                fh.write(f"{res.title}\nAutor: {res.creator}\nLicencia: {res.license}\nFuente: {res.source}\nPágina: {res.page_url}\n")
            self.events.put(("note", (f"Guardada en {base}.{ext} (créditos en .txt)", "ok")))
        except Exception as exc:
            self.events.put(("note", (f"No pude descargar la imagen: {exc}", "error")))

    def _open_result(self, res: SearchResult) -> None:
        if res.page_url:
            webbrowser.open(res.page_url)

    def _similar_result(self, res: SearchResult) -> None:
        self.lightbox = None
        self.input_text = res.title[:300]
        self._goto("create")

    # -------- voz
    def _stop_audio(self) -> None:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.speaking = False

    def _toggle_speak(self, text: str | None = None) -> None:
        if self.speaking:
            self._stop_audio()
            self._set_status("Lectura detenida")
            return
        if self.speak_loading:
            return
        text = clean_markdown(text if text is not None else self.last_answer).strip()
        if not text:
            self._set_status("Todavía no hay una respuesta para leer", "error")
            return
        self.speak_loading = True
        self._set_status("Preparando lectura en voz alta…", "working")
        threading.Thread(target=self._speak_worker, args=(text[:4500],), daemon=True).start()

    def _speak_worker(self, text: str) -> None:
        try:
            with io.BytesIO() as buffer:
                gTTS(text=text, lang="es").write_to_fp(buffer)
                data = buffer.getvalue()
            self.events.put(("audio_ready", data))
        except Exception as exc:
            self.events.put(("audio_error", f"No pude generar la voz. Detalle: {exc}"))

    # ------------------------------------------------------------------ eventos
    def _process_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind in {"text_done", "error"} and payload[0] != self.token:
                continue
            if kind == "text_done":
                self._add_msg("assistant", payload[1], origin=CHAT_ORIGIN)
                self.last_answer = payload[1]
                self.busy = False
                self._set_status("Respuesta lista")
            elif kind == "error":
                self._add_msg("assistant", payload[1], meta=True)
                self.busy = False
                self._set_status("No se pudo completar la solicitud", "error")
            elif kind == "audio_search_done":
                token, message = payload
                if token != self.token:
                    continue
                self._add_msg("assistant", message, origin="Búsqueda de audio · Wikimedia Commons")
                self.last_answer = message
                self.busy = False
                self._set_status("Búsqueda de audio terminada")
            elif kind == "audio_task_error":
                token, message = payload
                if token != self.token:
                    continue
                self._add_msg("assistant", message, meta=True)
                self.busy = False
                self._set_status("No se pudo generar el audio", "error")
            elif kind == "audio_generated":
                token, path, data = payload
                if token != self.token:
                    continue
                self._add_msg("assistant", f"Audio generado y guardado en MP3:\n{path}\n\nSe reproducirá ahora. Es voz sintetizada a partir del texto, no música ni efectos de sonido.", origin="gTTS · síntesis de voz")
                self.last_answer = f"Audio generado: {path}"
                self.busy = False
                try:
                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    self._audio_buf = io.BytesIO(data)
                    pygame.mixer.music.load(self._audio_buf, "mp3")
                    pygame.mixer.music.play()
                    self.speaking = True
                    self._set_status(f"MP3 guardado en {AUDIO_DIR} y reproduciéndose")
                except pygame.error as exc:
                    self._set_status(f"MP3 guardado, pero no se pudo reproducir: {exc}", "error")
            elif kind == "related_media":
                token, query, results = payload
                if token != self.token:
                    continue
                sid = next(self.search_ids)
                entry = {"kind": "search", "sid": sid, "query": query, "results": results, "waiting": 0}
                self.feed.append(entry)
                for res in results:
                    self.thumb_q.put(res)
                self.scroll = 10**7
            elif kind == "img_status":
                entry = next((e for e in self.feed if e["kind"] == "pending" and e["job"]["id"] == payload[0]), None)
                if entry:
                    entry["job"]["status"] = payload[1]
            elif kind == "img_done":
                jid, image, used = payload
                label = PROVIDER_LABELS[used]
                idx = next((i for i, e in enumerate(self.feed) if e["kind"] == "pending" and e["job"]["id"] == jid), None)
                if idx is not None:
                    job = self.feed[idx]["job"]
                    surface = pygame.image.fromstring(image.tobytes(), image.size, "RGB")
                    item = GalleryItem(image, surface, job["prompt"], job["full"], label, job["provider"], job["size"], used)
                    self.feed[idx] = {"kind": "image", "item": item}
                    if idx == len(self.feed) - 1:
                        self.scroll = 10**7
                    o_kind, o_detail = provider_origin(used)
                    self._set_status(f"Imagen lista · {ORIGIN_BADGE[o_kind]} · {o_detail}")
            elif kind == "img_fail":
                jid, message = payload
                idx = next((i for i, e in enumerate(self.feed) if e["kind"] == "pending" and e["job"]["id"] == jid), None)
                if idx is not None:
                    del self.feed[idx]
                    self._add_msg("assistant", f"No pude crear la imagen con {message}", meta=True)
                self._set_status("No se pudo crear la imagen", "error")
            elif kind == "enhance_done":
                self.enhancing = False
                self.input_text = payload
                self._set_status("Prompt mejorado: revísalo y pulsa Crear")
            elif kind == "enhance_fail":
                self.enhancing = False
                self._set_status(f"No pude mejorar el prompt: {payload}"[:140], "error")
            elif kind == "search_part":
                sid, _label, results = payload
                entry = self._search_entry(sid)
                if entry is None:
                    continue
                entry["waiting"] -= 1
                for res in results:
                    entry["results"].append(res)
                    self.thumb_q.put(res)
                self._finish_search_status(entry)
            elif kind == "search_fail":
                sid, label, err = payload
                entry = self._search_entry(sid)
                if entry is None:
                    continue
                entry["waiting"] -= 1
                self._set_status(f"{label} no respondió: {err}"[:140], "error")
            elif kind == "thumb":
                res, img = payload
                if img is None:
                    res.failed = True
                else:
                    res.surface = pygame.image.fromstring(img.tobytes(), img.size, "RGB")
            elif kind == "full":
                res, img = payload
                res.full_loading = False
                if img is not None:
                    res.full_surface = pygame.image.fromstring(img.tobytes(), img.size, "RGB")
            elif kind == "note":
                self._set_status(payload[0], payload[1])
            elif kind == "audio_ready":
                self.speak_loading = False
                try:
                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    self._audio_buf = io.BytesIO(payload)
                    pygame.mixer.music.load(self._audio_buf, "mp3")
                    pygame.mixer.music.play()
                    self.speaking = True
                    self._set_status("Reproduciendo respuesta")
                except pygame.error as exc:
                    self._set_status(f"No se pudo reproducir audio: {exc}", "error")
            elif kind == "audio_error":
                self.speak_loading = False
                self._set_status(payload, "error")
        if self.speaking:
            try:
                if not pygame.mixer.music.get_busy():
                    self.speaking = False
                    self._set_status("Listo")
            except pygame.error:
                self.speaking = False

    def _finish_search_status(self, entry: dict[str, Any]) -> None:
        if entry["waiting"] <= 0:
            if entry["results"]:
                self._set_status(f"{len(entry['results'])} imágenes encontradas")
            else:
                self._set_status("Sin resultados. Prueba con otras palabras.", "error")

    def _handle_mouse(self, position: tuple[int, int]) -> None:
        for rect, action in reversed(self.buttons):
            if rect.collidepoint(position):
                action()
                return

    def _handle_event(self, event: pygame.event.Event) -> None:
        if self.phase == "intro":
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self._skip_intro()
            return
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == getattr(pygame, "WINDOWMAXIMIZED", -1):
            self.maximized = True
        elif event.type == getattr(pygame, "WINDOWRESTORED", -1):
            self.maximized = False
        elif event.type == pygame.VIDEORESIZE:
            # Windows/pygame redimensionan la superficie automáticamente.
            # No recrear set_mode() durante el redimensionado: puede parpadear.
            self.screen = pygame.display.get_surface() or self.screen
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            if self.lightbox is None:
                self.scroll = max(0, self.scroll - event.y * 60)
        elif event.type == pygame.KEYDOWN:
            ctrl = event.mod & pygame.KMOD_CTRL
            if event.key == pygame.K_F11:
                self._toggle_maximize()
            elif event.key == pygame.K_ESCAPE:
                if self.menu is not None:
                    self.menu = None
                elif self.lightbox is not None:
                    self.lightbox = None
                else:
                    self.input_text = ""
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if ctrl:
                    self._quick_create()
                elif event.mod & pygame.KMOD_SHIFT:
                    self.input_text = (self.input_text + "\n")[:MAX_INPUT]
                else:
                    self._submit()
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = re.sub(r"\S*\s*$", "", self.input_text) if ctrl else self.input_text[:-1]
            elif event.key == pygame.K_PAGEUP:
                self.scroll = max(0, self.scroll - self.feed_rect.height + 80)
            elif event.key == pygame.K_PAGEDOWN:
                self.scroll += self.feed_rect.height - 80
            elif ctrl and event.key == pygame.K_v:
                self._paste()
            elif ctrl and event.key == pygame.K_n:
                self._new_chat()
            elif event.unicode and event.unicode.isprintable() and not ctrl:
                self.menu = None
                if len(self.input_text) < MAX_INPUT:
                    self.input_text += event.unicode

    def run(self) -> None:
        try:
            while self.running:
                for event in pygame.event.get():
                    self._handle_event(event)
                self._process_events()
                if self.phase == "intro":
                    self._tick_intro()
                self.draw()
                self.clock.tick(60)
        finally:
            pygame.quit()


def main() -> None:
    try:
        ElinApp().run()
    except Exception as exc:
        pygame.quit()
        raise SystemExit(f"No se pudo iniciar ELIN: {exc}") from exc


if __name__ == "__main__":
    main()
