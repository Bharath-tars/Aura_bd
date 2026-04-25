"""
Landing page image generator — Gemini "Nano Banana" image generation
(model: gemini-3.1-flash-image-preview, fallback: imagen-3.0-generate-002)

Run ONCE before serving the app:
    cd aura/backend
    python generate_landing_images.py

Saves PNG images to:  ../frontend/public/landing/
The React landing page references them as static assets: /landing/<name>.png

Docs: https://ai.google.dev/gemini-api/docs/image-generation
"""
import io
import os
import sys
from pathlib import Path

# ── Load API key ──────────────────────────────────────────────────────────────
API_KEY = os.getenv("GEMINI_API_KEY", "")
if not API_KEY:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip()
                break

if not API_KEY:
    sys.exit("ERROR: GEMINI_API_KEY not found. Set it in .env or as an env var.")

# ── Lazy imports (so the error message above fires before any import noise) ──
try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    sys.exit("ERROR: run  pip install google-genai Pillow")

try:
    from PIL import Image
except ImportError:
    sys.exit("ERROR: run  pip install Pillow")

# ── Output directory ──────────────────────────────────────────────────────────
OUT = Path(__file__).parent.parent / "frontend" / "public" / "landing"
OUT.mkdir(parents=True, exist_ok=True)

client = genai.Client(api_key=API_KEY)

# ── Image definitions ─────────────────────────────────────────────────────────
IMAGES = [
    dict(
        name="hero",
        aspect="16:9",
        prompt=(
            "Ultra-wide abstract neural network floating in deep space. Thousands of "
            "luminous nodes in indigo, violet, and soft emerald connected by delicate "
            "glowing threads that pulse gently. Dark navy background. The network loosely "
            "resembles a human brain viewed from above. Cinematic depth-of-field, "
            "photorealistic 3D render. No text, no labels."
        ),
    ),
    dict(
        name="crisis",
        aspect="16:9",
        prompt=(
            "Minimalist world map as a constellation of pulsing amber and rose dots, each "
            "dot a city where mental health care is needed. Bright dots = access to care, "
            "dim dots = the treatment gap. Deep dark navy background. "
            "Aerial data-art aesthetic, cinematic. No text, no country labels."
        ),
    ),
    dict(
        name="coach",
        aspect="4:3",
        prompt=(
            "Soft morning light on a person sitting peacefully at a window, holding a "
            "glowing phone showing a calm AI chat interface in indigo and white. Minimal "
            "room: warm wood, single plant, bokeh background. The person's expression: "
            "thoughtful and relieved. Lifestyle photography, golden hour, shallow depth of "
            "field. No visible text on the phone."
        ),
    ),
    dict(
        name="tech",
        aspect="16:9",
        prompt=(
            "Stunning 3D visualization of eight glowing AI agent spheres — indigo, violet, "
            "emerald, cyan, rose, amber, teal, white — connected by flowing data streams and "
            "light trails orbiting a central core. Deep dark background with subtle particle "
            "dust. Tech-art, cinematic render. No text labels on the spheres."
        ),
    ),
    dict(
        name="journal",
        aspect="4:3",
        prompt=(
            "Open notebook with softly glowing pages on a warm wooden desk. Steaming tea cup "
            "beside it. Gentle afternoon light, a plant casting leaf shadows. The writing "
            "appears to emit a subtle data-aura — as if being quietly understood by an "
            "unseen intelligence. Cozy editorial photography, warm tones, shallow focus. "
            "No readable text visible."
        ),
    ),
    dict(
        name="retention",
        aspect="1:1",
        prompt=(
            "Split visual: left side — a cold dark screen showing a generic wellness app "
            "with fading engagement (dimming stars, empty streaks). Right side — a warm "
            "glowing phone showing a 30-day streak in emerald, a personalised AI message. "
            "The contrast: cold/disconnected vs warm/known. Minimal modern graphic art, "
            "dark background. No readable text."
        ),
    ),
    dict(
        name="market",
        aspect="16:9",
        prompt=(
            "Abstract financial visualization: a soaring luminous arc from $448B to $573B "
            "rendered as a golden curve on deep dark background. Supporting glowing bars and "
            "orbiting circles in indigo and emerald represent TAM, SAM, ROI. "
            "Infographic art style, cinematic editorial quality. No readable numbers or text."
        ),
    ),
]


# ── Generator ─────────────────────────────────────────────────────────────────
def save_bytes(path: Path, data: bytes) -> None:
    img = Image.open(io.BytesIO(data))
    img.save(path, "PNG", optimize=True)
    print(f"   ✓  {path.name}  ({img.width}×{img.height})")


def generate(name: str, prompt: str, aspect: str) -> bool:
    out = OUT / f"{name}.png"
    if out.exists():
        print(f"   –  {name}.png  (already exists, skipping)")
        return True

    print(f"   ·  {name}.png  generating …")

    # Primary: gemini-3.1-flash-image-preview  (Nano Banana model)
    try:
        resp = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data is not None:
                save_bytes(out, part.inline_data.data)
                return True
    except Exception as e1:
        print(f"      flash-image failed: {e1}  → trying imagen-3 …")

    # Fallback: imagen-3.0-generate-002
    try:
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=gtypes.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect,
                output_mime_type="image/png",
            ),
        )
        if result.generated_images:
            save_bytes(out, result.generated_images[0].image.image_bytes)
            return True
    except Exception as e2:
        print(f"      imagen-3 also failed: {e2}")

    print(f"   ✗  {name}.png  — both models failed (gradient placeholder will show)")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n  Aura · Landing Image Generator")
    print(f"  Output → {OUT}\n")

    ok = sum(generate(i["name"], i["prompt"], i["aspect"]) for i in IMAGES)
    print(f"\n  {ok}/{len(IMAGES)} images ready.\n")
    if ok < len(IMAGES):
        print("  Missing images show gradient fallbacks — app still works.\n")


if __name__ == "__main__":
    main()
