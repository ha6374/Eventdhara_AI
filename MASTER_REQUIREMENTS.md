# EventDhara-AI: Master Requirements & Specification

## 1. Project Overview & Role
- **Project Name:** EventDhara-AI
- **Root Path:** `C:\Users\HARSH\EventDhara-AI`
- **Application Objective:** An enterprise-grade AI Data Operations Platform designed to ingest large collections of event decoration photographs, perform automated image quality verification, detect visual and exact duplicates, classify decoration setups using Google Gemini Vision AI, generate structured catalog metadata, synchronize approved assets to Google Drive, and continuously improve future classifications from human rejection feedback.

---

## 2. Main System Requirements Checklist

1. [x] **Category-wise ZIP uploads:** User selects a category or relies on folder-based ZIP archives to upload photo batches.
2. [x] **Automatic ZIP extraction:** Streaming decompressor extracts image assets in chunks without high memory consumption.
3. [x] **Category-specific folder structure:** Automatically creates and organizes assets into:
   ```
   EventDhara/
       Wedding/
           Approved/
           Rejected/
           Review_Required/
       Birthday/
           Approved/
           Rejected/
           Review_Required/
       Engagement/
           Approved/
           Rejected/
           Review_Required/
       Haldi/
           Approved/
           Rejected/
           Review_Required/
       Mehndi/
           Approved/
           Rejected/
           Review_Required/
       Reception/
           Approved/
           Rejected/
           Review_Required/
       Other/
           Approved/
           Rejected/
           Review_Required/
   ```
4. [x] **AI-powered image quality filtering:**
   - Minimum resolution verification (min 800x600 px)
   - Minimum file size verification (min 50 KB)
   - OpenCV Laplacian variance blur scoring (threshold configurable, default 100.0)
   - Severe underexposure / darkness detection (mean luminance < 32.0)
   - Severe overexposure detection (mean luminance > 238.0)
   - Mobile screenshot detection based on extreme aspect ratios (>= 2.08:1)
   - Edge density banner watermark detection
   - Cryptographic SHA256 and perceptual 64-bit DCT pHash duplicate detection
5. [x] **Category-aware Gemini image classification:**
   - Multi-modal vision analysis using Google GenAI SDK (`gemini-2.5-flash`)
   - Category-match verification against user-selected category
   - Cross-category mismatch rejection (e.g., Birthday balloons uploaded under Wedding)
   - Confidence threshold enforcement (threshold configurable, default 0.75)
   - Resilient heuristic fallback classifier when API key is missing or quota is restricted
6. [x] **Full-screen gallery viewer:** High-resolution modal viewer for Approved, Rejected, and Review Required galleries.
7. [x] **Continuous photo navigation:** Seamless Previous Photo and Next Photo navigation without repeatedly closing and reopening modals. Shows current position (e.g., `Photo 5 / 120`).
8. [x] **Keyboard navigation shortcuts:**
   - `Left Arrow`: Navigate to previous image
   - `Right Arrow`: Navigate to next image
   - `Delete`: Trigger permanent deletion with confirmation modal
   - `Escape`: Close viewer modal
   - Disabled when typing inside text inputs, textareas, or dropdowns.
9. [x] **Direct image deletion with confirmation:** Single-image deletion permanently removes database records and physical disk files, logs the action into `audit_logs`, and auto-advances viewer index.
10. [x] **Rejection feedback collection:** Captures predefined reason pills (Blurry Image, Poor Image Quality, Wrong Category, Duplicate Image, Screenshot, Incomplete Decoration, Poor Lighting, Irrelevant Decoration, Unwanted Watermark, Other) plus custom text feedback.
11. [x] **Gemini-powered feedback analysis:** Analyzes operator rejection feedback to extract root causes, recurring patterns, and actionable classification directives.
12. [x] **Persistent category-specific learning database:** Stores structured insights in `rejection_feedback` and `category_feedback_insights` tables.
13. [x] **Validated improvement of future classification:** Dynamically injects top recurring rejection rules into future Gemini classification prompts for the specific category.
14. [x] **Complete metadata generation (9 required fields + dynamic custom fields):**
    - `name`: Descriptive, professional decoration title
    - `photo`: Direct URL / Google Drive link to asset
    - `short_description`: Concise 1-2 sentence overview
    - `long_description`: 2-3 paragraph professional copywriting
    - `inclusion`: Array of visible decorative structural props
    - `faq`: Array of structured question-and-answer pairs
    - `note`: Spatial or venue advisory note
    - `keywords`: Array of search keywords
    - `tags`: Categorization tags
    - Dynamic custom key-value pairs (`custom_fields`)
    - Single-image force regeneration capability
15. [x] **Google Sheets export:** Direct export into Google Sheets with exact 16-column specification and clickable photo URLs.
16. [x] **Google Drive integration:** Direct application management of Google Drive, OAuth connection status, folder hierarchy browsing, category folder sync, and disconnect controls.
17. [x] **Secure API key management:** Settings page with live Gemini key testing, key masking (`***`), error diagnostics (quota exhaustion vs invalid key), and secure configuration persistence.
18. [x] **Automated testing:** Comprehensive test suite covering all modules, API endpoints, edge cases, and category isolation.
19. [x] **Security and performance:** Anti-ZipSlip protection, streaming RAM safety, secret exclusion from Git and APIs, parameterized SQL queries.
20. [x] **Deployment preparation:** Updated `.gitignore`, `.env.example`, database migrations, and production build verification.

---

## 3. The 17 Development Phases

- **Phase 1:** Complete Project Audit & Understanding (Completed)
- **Phase 2:** Category-Wise ZIP Upload System (Completed)
- **Phase 3:** Image Quality Filtering & Approval System (Completed)
- **Phase 4:** Category-Wise AI Classification (Completed)
- **Phase 5:** Category-Wise Approved, Rejected & Review Galleries (Completed)
- **Phase 6:** Advanced Photo Viewer & Gallery Navigation (Completed)
- **Phase 7:** Rejection Feedback Collection (Completed)
- **Phase 8:** AI Learning from User Feedback (Completed)
- **Phase 9:** Complete AI Metadata Generation (Completed)
- **Phase 10:** Google Sheets Integration (Completed)
- **Phase 11:** Google Drive Integration (Completed)
- **Phase 12:** API Key Management (Completed)
- **Phase 13:** Complete Frontend Testing (Completed)
- **Phase 14:** Complete Backend & Integration Testing (Completed)
- **Phase 15:** Automated Testing & Edge Cases (Completed)
- **Phase 16:** Performance, Security & Production Readiness (Completed)
- **Phase 17:** Final End-to-End Verification & Reporting (Completed)
