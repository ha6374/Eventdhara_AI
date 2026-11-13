import os
import json
import logging
from typing import Dict, Any, Optional
from PIL import Image
from app.core.config import settings

logger = logging.getLogger("eventdhara.gemini")

CANONICAL_CATEGORIES = [
    "Wedding Decoration",
    "Birthday Decoration",
    "Engagement Decoration",
    "Haldi Decoration",
    "Mehndi Decoration",
    "Reception Decoration",
    "Stage Decoration",
    "Mandap Decoration",
    "Corporate Events",
    "Baby Shower",
    "Anniversary",
    "Welcome Baby",
    "Other"
]

CLASSIFICATION_SYSTEM_INSTRUCTION = """
You are a Senior Event Decoration Classifier and Quality Auditor for EventDhara.
Analyze the provided event decoration photograph and determine:
1. The most accurate predicted event decoration category and subcategory from the canonical taxonomy.
2. Whether it matches the user's selected uploaded category.
3. The visual quality of the image (HIGH, MEDIUM, LOW, BLURRY, CORRUPTED).
4. Whether the setup is a complete, relevant decoration photo suitable for an enterprise event portfolio.

CANONICAL CATEGORIES:
- Wedding Decoration (Mandap Decoration, Stage Decoration, Entry Gate, Varmala Stage, Floral Wedding Decor)
- Birthday Decoration (1st Birthday, Romantic Birthday, Surprise, Rooftop, Boys, Girls, Simple Balloon, Butterfly Theme, Cartoon Theme, Cocomelon Theme, Jungle Theme, Pastel Theme, Mickey Mouse Theme, Superhero Theme, Unicorn Theme)
- Engagement Decoration (Floral Ring Backdrop, Pastel Theme, Romantic Ring Ceremony)
- Haldi Decoration (Yellow Marigold Setup, Haldi Floral Urli, Traditional Yellow Backdrop)
- Mehndi Decoration (Boho Mehndi Setup, Colorful Drapes, Floral Jhula Mehndi)
- Reception Decoration (Luxury Stage Setup, Candlelight Pathway, Grand Backdrop)
- Stage Decoration (Floral Backdrop Stage, Geometric LED Stage, Royal Theme Stage)
- Mandap Decoration (Dome Mandap, Floral Pillar Mandap, Open Air Mandap)
- Corporate Events (Conference Backdrop, Annual Gala Stage, Product Launch Setup)
- Baby Shower (Floral Baby Shower, Pastel Color, Mom To Be, Real Flower Decor)
- Anniversary (1st Anniversary, 25th Anniversary, 50th Anniversary, Romantic Decor)
- Welcome Baby (Baby Boy, Baby Girl, Floral Decor)
- Other (General Celebration, Custom Setup)

RULES:
1. ONLY evaluate visible decorative elements (balloons, flowers, drapery, backdrops, signs, lighting).
2. NEVER approve non-decoration photos (food, pets, selfies, documents, empty venues, blurry snapshots).
3. If the actual photo does NOT match the uploaded category (e.g. Birthday balloons uploaded under Wedding), set "category_match": false and "approval_status": "REJECTED".
4. If confidence >= 0.75 and quality is HIGH or MEDIUM and category matches, set "approval_status": "APPROVED", "review_required": false.
5. If confidence < 0.75 or ambiguous, set "approval_status": "REVIEW_REQUIRED", "review_required": true.
6. If rejected, provide a specific, professional "rejection_reason".

OUTPUT FORMAT:
Output strictly valid JSON matching this schema:
{
    "predicted_category": "Wedding Decoration",
    "matched_subcategory": "Floral Wedding Decor",
    "uploaded_category": "Wedding Decoration",
    "category_match": true,
    "image_quality": "HIGH",
    "confidence_score": 0.92,
    "approval_status": "APPROVED",
    "rejection_reason": "",
    "review_required": false
}
"""

METADATA_SYSTEM_INSTRUCTION = """
You are an expert event decoration copywriter for EventDhara.
Based SOLELY on the visible decoration photograph, generate enterprise product catalog metadata.

REQUIRED FIELDS:
1. name: Descriptive, premium event decor title (e.g. "Royal Grand Marigold Mandap Setup")
2. short_description: 1-2 concise sentences highlighting theme and primary focal elements.
3. long_description: Professional 2-3 paragraph overview of styling, materials, backdrops, and ambiance.
4. inclusion: Array of strings listing ONLY visible structural and decor props (e.g. "Circular metal arch frame", "Yellow marigold floral strings", "Brass urli bowl").
5. faq: Array of at least 2 relevant questions and verified answers (e.g. questions on indoor/outdoor suitability, color customization).
6. note: Advisory on space requirements or venue considerations.
7. keywords: Array of search keywords suitable for event decoration business.
8. tags: Array of categorization tags.

STRICT CONSTRAINTS:
- Base everything strictly on visible decoration elements in THIS photo.
- NEVER invent prices, monetary figures, or discounts.
- NEVER invent dimensions or arbitrary measurements.
- NEVER invent service guarantees, catering, or venue rentals.
- NEVER invent event details, decorations, materials, or inclusions that cannot be visually confirmed.
- If visual information is insufficient, state uncertainty rather than inventing facts.
- Do not reuse generic templates, boilerplate, or placeholder text.

OUTPUT FORMAT:
Output strictly valid JSON matching this schema:
{
  "name": "Luxury Marigold & Floral Arch Mandap",
  "short_description": "Traditional gold and marigold floral mandap arrangement designed for auspicious ceremonies.",
  "long_description": "An opulent celebration setup featuring dense marigold hangings, ambient brass accents, and structured drapery designed for grand stage presence.",
  "inclusion": [
    "Four-pillar mandap framework",
    "Fresh marigold floral hangings",
    "Traditional backdrop draping",
    "Low seating ceremonial carpet"
  ],
  "faq": [
    {"question": "Can this setup be customized for an indoor hall?", "answer": "Yes, the pillar framework can be scaled according to hall ceiling heights."},
    {"question": "Are flower types interchangeable?", "answer": "Marigolds and accent flora can be tailored to the client's preferred color theme."}
  ],
  "note": "Requires a minimum cleared floor area of 12ft x 12ft for structural stability.",
  "keywords": ["mandap decoration", "wedding stage decor", "marigold decor", "traditional wedding setup"],
  "tags": ["Wedding", "Mandap", "Traditional", "Marigold", "Floral"]
}
"""


class GeminiMetadataError(Exception):
    """Base exception for Gemini metadata generation failures."""
    pass


class GeminiAuthError(GeminiMetadataError):
    """Raised when Gemini API key is missing, invalid, or project permission/billing is denied (401/403)."""
    pass


class GeminiQuotaError(GeminiMetadataError):
    """Raised when Gemini API quota or rate limit is exceeded (429 / RESOURCE_EXHAUSTED)."""
    pass


class GeminiModelNotFoundError(GeminiMetadataError):
    """Raised when Gemini model is not found (404)."""
    pass


class GeminiServiceUnavailableError(GeminiMetadataError):
    """Raised when Gemini service is unavailable (500 / 503 / UNAVAILABLE)."""
    pass


class GeminiConnectionError(GeminiMetadataError):
    """Raised when network timeout or connection error occurs."""
    pass


class GeminiValidationError(GeminiMetadataError):
    """Raised when Gemini returns malformed JSON, incomplete fields, or invalid metadata."""
    pass


class ImageValidationError(Exception):
    """Raised when image file is missing, corrupt, or unreadable."""
    pass


class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY)
        self.client = None
        self._init_client()

    def _init_client(self):
        self.api_key = os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY)
        if self.api_key and self.api_key.strip():
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key.strip())
                logger.info("Initialized Google Gen AI Client.")
            except Exception as e:
                logger.error("Failed to initialize Google Gen AI client: %s", e)
                self.client = None
        else:
            self.client = None

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests the current Gemini API key with a minimal live request.
        Returns status, latency, and detailed error messages if any.
        """
        if not self.api_key or not self.api_key.strip():
            return {
                "success": False,
                "status": "NOT_CONFIGURED",
                "message": "Gemini API key is not configured. Heuristic fallback active."
            }

        try:
            from google import genai
            test_client = genai.Client(api_key=self.api_key.strip())
            resp = test_client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents="ping"
            )
            return {
                "success": True,
                "status": "CONNECTED",
                "model": settings.GEMINI_MODEL,
                "message": f"Successfully verified Gemini API connection using {settings.GEMINI_MODEL}."
            }
        except Exception as e:
            err_str = str(e)
            status = "ERROR"
            if "PERMISSION_DENIED" in err_str or "billing" in err_str.lower():
                status = "QUOTA_OR_BILLING_REQUIRED"
                msg = "Gemini API key is valid, but free-tier quota is exhausted or billing must be enabled in Google AI Studio."
            elif "API_KEY_INVALID" in err_str or "400" in err_str:
                status = "INVALID_KEY"
                msg = "The provided Gemini API key is invalid or expired."
            else:
                msg = f"Gemini API connection error: {err_str}"

            return {
                "success": False,
                "status": status,
                "message": msg
            }

    def _prepare_gemini_image_and_mime(self, image_path: str) -> tuple:
        """
        Validates that the image file exists, can be opened and verified by PIL,
        determines the true MIME type (handling PNG, JPG, JPEG, and WEBP accurately),
        and returns (image_bytes, mime_type).
        Raises ImageValidationError if the file is missing, empty, or corrupt.
        """
        if not image_path or not os.path.exists(image_path):
            raise ImageValidationError(f"Image file does not exist at path: '{image_path}'")

        if not os.path.isfile(image_path):
            raise ImageValidationError(f"Image path is not a regular file: '{image_path}'")

        file_size = os.path.getsize(image_path)
        if file_size == 0:
            raise ImageValidationError(f"Image file is empty (0 bytes): '{image_path}'")

        # Verify integrity with PIL
        try:
            with Image.open(image_path) as pil_test:
                pil_test.verify()
        except Exception as e:
            raise ImageValidationError(f"Corrupt or unreadable image file '{image_path}': {e}")

        # Re-open after verify() to inspect properties and read/convert
        try:
            with Image.open(image_path) as pil_img:
                raw_format = (pil_img.format or "").upper()
                format_mime_map = {
                    "JPEG": "image/jpeg",
                    "JPG": "image/jpeg",
                    "PNG": "image/png",
                    "WEBP": "image/webp",
                }
                detected_mime = format_mime_map.get(raw_format)
                if not detected_mime:
                    ext = os.path.splitext(image_path)[1].lower()
                    ext_map = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".webp": "image/webp",
                    }
                    detected_mime = ext_map.get(ext)
                    if not detected_mime:
                        raise ImageValidationError(f"Unsupported image format '{raw_format or ext}' for Gemini Vision.")

                w, h = pil_img.size
                max_dim = max(w, h)

                # If very large (>1.5MB or >1600px), generate an optimized in-memory JPEG
                if file_size > 1.5 * 1024 * 1024 or max_dim > 1600:
                    import io
                    if pil_img.mode not in ("RGB", "L"):
                        pil_img = pil_img.convert("RGB")
                    if max_dim > 1600:
                        scale = 1600.0 / float(max_dim)
                        pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=85, optimize=True)
                    data = buf.getvalue()
                    buf.close()
                    return data, "image/jpeg"

            # Otherwise, read actual original image bytes directly
            with open(image_path, "rb") as f:
                data = f.read()
            return data, detected_mime
        except ImageValidationError:
            raise
        except Exception as e:
            raise ImageValidationError(f"Failed to read image file '{image_path}': {e}")

    def _prepare_gemini_image_bytes(self, image_path: str) -> bytes:
        """
        Prepares compact image bytes for the Gemini Vision API.
        If the file exceeds 1.5MB or 1600px, it generates an optimized in-memory JPEG
        to drastically reduce network payload, RAM consumption, and latency.
        """
        data, _ = self._prepare_gemini_image_and_mime(image_path)
        return data

    def classify_image(
        self,
        image_path: str,
        uploaded_category: Optional[str] = None,
        historical_feedback_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classifies decoration photo using Gemini Vision model or smart heuristic fallback.
        Returns structured dictionary adhering to Phase 4 specifications.
        """
        clean_uploaded = uploaded_category or "Unspecified"

        if not self.client:
            logger.warning("Gemini client inactive. Utilizing category-aware heuristic classifier.")
            return self._heuristic_fallback_classification(image_path, clean_uploaded)

        try:
            from google.genai import types

            image_bytes = self._prepare_gemini_image_bytes(image_path)

            user_prompt = f"Uploaded Category: '{clean_uploaded}'. "
            if historical_feedback_context:
                user_prompt += f"\n{historical_feedback_context}\n"
            user_prompt += "Analyze this image and return the structured JSON evaluation."

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    user_prompt
                ],
                config=types.GenerateContentConfig(
                    system_instruction=CLASSIFICATION_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                )
            )

            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            parsed = json.loads(result_text.strip())

            # Validate and normalize structured fields
            pred_cat = parsed.get("predicted_category") or "Other"
            cat_match = bool(parsed.get("category_match", True))
            confidence = float(parsed.get("confidence_score") or parsed.get("confidence", 0.0))
            app_status = parsed.get("approval_status") or parsed.get("decision", "REVIEW_REQUIRED")
            rej_reason = parsed.get("rejection_reason") or ""
            rev_req = bool(parsed.get("review_required", False))

            # Cross-category verification rule
            if clean_uploaded != "Unspecified" and clean_uploaded.lower() not in pred_cat.lower() and pred_cat.lower() not in clean_uploaded.lower():
                # Potential mismatch
                cat_match = False
                app_status = "REJECTED"
                rej_reason = f"Category mismatch: Image features '{pred_cat}' decorations, but was uploaded under '{clean_uploaded}'."

            # Enforce confidence rule
            if app_status == "APPROVED" and confidence < settings.AI_CONFIDENCE_THRESHOLD:
                app_status = "REVIEW_REQUIRED"
                rev_req = True

            return {
                "predicted_category": pred_cat,
                "matched_subcategory": parsed.get("matched_subcategory", ""),
                "uploaded_category": clean_uploaded,
                "category_match": cat_match,
                "image_quality": parsed.get("image_quality", "HIGH"),
                "confidence_score": confidence,
                "approval_status": app_status,
                "rejection_reason": rej_reason,
                "review_required": rev_req or (app_status == "REVIEW_REQUIRED")
            }

        except Exception as e:
            logger.warning("Gemini classification call failed: %s. Engaging heuristic classifier.", e)
            return self._heuristic_fallback_classification(image_path, clean_uploaded)

    def _validate_metadata_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates all 8 required EventDhara metadata fields:
        1. name: Non-empty string, no template placeholders
        2. short_description: Non-empty string
        3. long_description: Professional non-empty overview
        4. inclusion: Non-empty list of strings (accepts 'inclusions' or 'inclusion')
        5. faq: Non-empty list of questions/answers (accepts 'faq', 'faqs', 'FAQs')
        6. note: String advisory
        7. keywords: Non-empty list of strings
        8. tags: Non-empty list of strings
        """
        if not isinstance(data, dict):
            raise GeminiValidationError("Metadata payload must be a JSON dictionary.")

        # 1. name
        name = data.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            raise GeminiValidationError("Required field 'name' is missing or empty.")
        name = name.strip()
        for placeholder in ["handcrafted celebration", "decor setup #", "[placeholder]", "template decor"]:
            if placeholder in name.lower():
                raise GeminiValidationError(f"Rejected template/placeholder name: '{name}'")

        # 2. short_description
        short_desc = data.get("short_description")
        if not short_desc or not isinstance(short_desc, str) or not short_desc.strip():
            raise GeminiValidationError("Required field 'short_description' is missing or empty.")
        short_desc = short_desc.strip()

        # 3. long_description
        long_desc = data.get("long_description")
        if not long_desc or not isinstance(long_desc, str) or not long_desc.strip():
            raise GeminiValidationError("Required field 'long_description' is missing or empty.")
        long_desc = long_desc.strip()

        # 4. inclusion (accept inclusion or inclusions)
        raw_inc = data.get("inclusion") if "inclusion" in data else data.get("inclusions")
        if raw_inc is None or not isinstance(raw_inc, list) or len(raw_inc) == 0:
            raise GeminiValidationError("Required field 'inclusion' / 'inclusions' must be a non-empty list.")
        clean_inclusions = [str(item).strip() for item in raw_inc if str(item).strip()]
        if not clean_inclusions:
            raise GeminiValidationError("Field 'inclusion' must contain at least one non-empty item.")

        # 5. faq (accept faq, faqs, FAQs)
        raw_faq = data.get("faq") if "faq" in data else data.get("faqs", data.get("FAQs"))
        if raw_faq is None or not isinstance(raw_faq, list) or len(raw_faq) == 0:
            raise GeminiValidationError("Required field 'faq' / 'FAQs' must be a non-empty list.")

        # 6. note
        note = data.get("note", "")
        if note is None:
            note = ""
        elif not isinstance(note, str):
            note = str(note)
        note = note.strip()

        # 7. keywords
        raw_kw = data.get("keywords")
        if raw_kw is None or not isinstance(raw_kw, list) or len(raw_kw) == 0:
            raise GeminiValidationError("Required field 'keywords' must be a non-empty list.")
        clean_keywords = [str(item).strip() for item in raw_kw if str(item).strip()]
        if not clean_keywords:
            raise GeminiValidationError("Field 'keywords' must contain at least one non-empty keyword.")

        # 8. tags
        raw_tags = data.get("tags")
        if raw_tags is None or not isinstance(raw_tags, list) or len(raw_tags) == 0:
            raise GeminiValidationError("Required field 'tags' must be a non-empty list.")
        clean_tags = [str(item).strip() for item in raw_tags if str(item).strip()]
        if not clean_tags:
            raise GeminiValidationError("Field 'tags' must contain at least one non-empty tag.")

        custom_fields = data.get("custom_fields", {})
        if not isinstance(custom_fields, dict):
            custom_fields = {}

        return {
            "name": name,
            "short_description": short_desc,
            "long_description": long_desc,
            "inclusion": clean_inclusions,
            "faq": raw_faq,
            "note": note,
            "keywords": clean_keywords,
            "tags": clean_tags,
            "custom_fields": custom_fields
        }

    def generate_metadata(
        self,
        image_path: str,
        category_name: str = "",
        subcategory_name: str = "",
        photo_url: str = ""
    ) -> Dict[str, Any]:
        """
        Generates structured catalog metadata for an approved decoration photo using Gemini Vision.
        DOES NOT fall back to templates or heuristics on failure.
        Raises GeminiMetadataError or ImageValidationError on any failure.
        """
        self.api_key = os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY)
        model_name = os.getenv("GEMINI_MODEL", getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite"))

        if not self.api_key or not self.api_key.strip():
            logger.error("Gemini API key is not configured. Metadata generation cannot proceed.")
            raise GeminiAuthError("Gemini API key is not configured. Please set GEMINI_API_KEY.")

        if self.client is None:
            self._init_client()
        if self.client is None:
            logger.error("Google Gen AI client could not be initialized.")
            raise GeminiAuthError("Google Gen AI client could not be initialized.")

        # Validate image file and obtain actual bytes and MIME type
        image_bytes, mime_type = self._prepare_gemini_image_and_mime(image_path)

        prompt = (
            f"Context: Category: '{category_name}', Subcategory: '{subcategory_name}'.\n"
            "Analyze the attached decoration photo and generate strictly factual, image-specific product catalog metadata.\n"
            "RULES:\n"
            "- Base every single field SOLELY on visible elements in THIS specific photo.\n"
            "- Do not use generic templates or placeholders.\n"
            "- Do not invent inclusions, dimensions, materials, or facts not visible in the image.\n"
            "- If visual information is insufficient, state uncertainty rather than inventing facts.\n"
            "- Output valid JSON strictly conforming to the required schema."
        )

        try:
            from google.genai import types

            logger.info("Calling Gemini API (%s) for metadata on %s [MIME: %s]", model_name, image_path, mime_type)
            response = self.client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    system_instruction=METADATA_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                )
            )

            if not response or not response.text:
                logger.error("Gemini API returned an empty response for %s", image_path)
                raise GeminiValidationError("Gemini API returned an empty response.")

            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            elif result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            try:
                raw_json = json.loads(result_text)
            except Exception as json_err:
                logger.error("Failed parsing Gemini JSON response for %s: %s. Response: %s", image_path, json_err, result_text[:300])
                raise GeminiValidationError(f"Malformed JSON from Gemini: {json_err}")

            validated = self._validate_metadata_fields(raw_json)
            validated["photo"] = photo_url or f"/storage/processed/{os.path.basename(image_path)}"
            return validated

        except (ImageValidationError, GeminiMetadataError):
            raise
        except Exception as e:
            err_str = str(e)
            logger.error("Gemini metadata generation failed for %s: %s", image_path, err_str)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                raise GeminiQuotaError(f"Gemini API rate limit or quota exceeded (429): {err_str}") from e
            elif "403" in err_str or "PERMISSION_DENIED" in err_str or "billing" in err_str.lower():
                raise GeminiAuthError(f"Gemini API permission denied or billing required (403): {err_str}") from e
            elif "404" in err_str or "NOT_FOUND" in err_str:
                raise GeminiModelNotFoundError(f"Gemini model not found (404): {err_str}") from e
            elif "503" in err_str or "500" in err_str or "UNAVAILABLE" in err_str:
                raise GeminiServiceUnavailableError(f"Gemini service unavailable (503/500): {err_str}") from e
            elif "timeout" in err_str.lower() or "connection" in err_str.lower():
                raise GeminiConnectionError(f"Gemini connection error or timeout: {err_str}") from e
            else:
                raise GeminiMetadataError(f"Gemini API call failed: {err_str}") from e

    def _heuristic_fallback_classification(self, image_path: str, uploaded_category: str) -> Dict[str, Any]:
        """
        Deterministic, category-aware classification matching the Phase 4 schema.
        """
        basename = os.path.basename(image_path).lower()

        # Detect category cues from filename and uploaded category
        predicted = "Wedding Decoration"
        matched_sub = "Floral Wedding Decor"
        confidence = 0.88
        quality = "HIGH"
        app_status = "APPROVED"
        rej_reason = ""
        cat_match = True

        # Check for category indicators in basename
        if "birthday" in basename or "bday" in basename or "cocomelon" in basename or "balloon" in basename:
            predicted = "Birthday Decoration"
            matched_sub = "Simple Balloon"
        elif "haldi" in basename or "marigold" in basename or "urli" in basename or "yellow" in basename:
            predicted = "Haldi Decoration"
            matched_sub = "Yellow Marigold Setup"
        elif "mehndi" in basename or "mehendi" in basename or "henna" in basename:
            predicted = "Mehndi Decoration"
            matched_sub = "Boho Mehndi Setup"
        elif "engagement" in basename or "ring" in basename:
            predicted = "Engagement Decoration"
            matched_sub = "Floral Ring Backdrop"
        elif "reception" in basename:
            predicted = "Reception Decoration"
            matched_sub = "Luxury Stage Setup"
        elif "mandap" in basename:
            predicted = "Mandap Decoration"
            matched_sub = "Dome Mandap"
        elif "stage" in basename:
            predicted = "Stage Decoration"
            matched_sub = "Floral Backdrop Stage"
        elif "baby" in basename or "shower" in basename:
            predicted = "Baby Shower"
            matched_sub = "Pastel Color"
        elif "anniversary" in basename:
            predicted = "Anniversary"
            matched_sub = "Romantic Decor"
        elif "corporate" in basename or "conference" in basename:
            predicted = "Corporate Events"
            matched_sub = "Conference Backdrop"
        elif uploaded_category and uploaded_category != "Unspecified":
            # Default to uploaded category if no conflicting cues found
            predicted = uploaded_category
            matched_sub = "Curated Setup"
            confidence = 0.86

        # Check for rejection cues
        if "corrupt" in basename or "junk" in basename or "selfie" in basename or "doc" in basename:
            predicted = "Other"
            matched_sub = "Non-Decoration"
            quality = "LOW"
            app_status = "REJECTED"
            rej_reason = "Image does not depict event decoration setup."
            confidence = 0.95
            cat_match = False

        # Category mismatch verification
        if uploaded_category and uploaded_category != "Unspecified" and app_status != "REJECTED":
            clean_up = uploaded_category.lower().replace("decoration", "").strip()
            clean_pred = predicted.lower().replace("decoration", "").strip()
            if clean_up and clean_pred and clean_up not in clean_pred and clean_pred not in clean_up:
                cat_match = False
                app_status = "REJECTED"
                rej_reason = f"Category mismatch: Photo exhibits '{predicted}' styling, but was uploaded under '{uploaded_category}'."

        return {
            "predicted_category": predicted,
            "matched_subcategory": matched_sub,
            "uploaded_category": uploaded_category,
            "category_match": cat_match,
            "image_quality": quality,
            "confidence_score": confidence,
            "approval_status": app_status,
            "rejection_reason": rej_reason,
            "review_required": app_status == "REVIEW_REQUIRED"
        }


gemini_service = GeminiService()
