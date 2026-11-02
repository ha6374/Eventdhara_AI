"""
EventDhara AI Platform - Demo Data Seeder
Generates clearly labeled demonstration decoration images and runs them
through the ingestion pipeline to demonstrate real PostgreSQL-connected functionality.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.database import SessionLocal, Base, engine
from app.models.category import Category
from app.services.category_service import CategoryService
from app.services.processing_service import ProcessingService
from app.services.metadata_service import MetadataService
from app.services.drive_service import GoogleDriveService

DEMO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "demo_source"))
os.makedirs(DEMO_DIR, exist_ok=True)


def create_demo_image(
    filename: str,
    title: str,
    category_label: str,
    color_palette: list,
    blur: bool = False
) -> str:
    width, height = 1200, 900
    # Background gradient
    img = Image.new("RGB", (width, height), color=color_palette[0])
    draw = ImageDraw.Draw(img)

    # Decorative shapes (balloons / arches)
    for i in range(12):
        x = 100 + i * 85
        y = 200 + int(np.sin(i * 0.5) * 80)
        r = 60 + (i % 3) * 15
        color = color_palette[(i % (len(color_palette) - 1)) + 1]
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline=(255, 255, 255), width=2)
        # Balloon string
        draw.line([x, y + r, x, y + r + 150], fill=(200, 200, 200), width=2)

    # Frame Backdrop
    draw.rectangle([200, 350, 1000, 800], outline=(220, 220, 220), width=6)

    # Text
    draw.rectangle([250, 450, 950, 650], fill=(0, 0, 0, 120))
    draw.text((300, 480), f"[DEMO] {title}", fill=(255, 255, 255))
    draw.text((300, 540), f"EventDhara Category: {category_label}", fill=(220, 240, 255))
    draw.text((300, 590), "Enterprise AI Photograph Operations Platform", fill=(180, 200, 220))

    if blur:
        import cv2
        np_img = np.array(img)
        # Apply heavy blur to trigger Laplacian blur failure
        blurred = cv2.GaussianBlur(np_img, (51, 51), 0)
        img = Image.fromarray(blurred)

    file_path = os.path.join(DEMO_DIR, filename)
    img.save(file_path, quality=95)
    return file_path


def seed_demo_pipeline():
    print("Connecting to PostgreSQL database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    cat_service = CategoryService(db)
    cat_service.seed_initial_categories()

    processor = ProcessingService(db)
    meta_service = MetadataService(db)
    drive_service = GoogleDriveService(db)

    print("Generating demo decoration photographs...")
    # 1. 1st Birthday Setup (Approved)
    p1 = create_demo_image(
        "demo_1st_birthday_safari.jpg",
        "1st Birthday Safari Balloon Garland",
        "Birthday Decoration -> 1st Birthday",
        [(24, 48, 89), (34, 197, 94), (234, 179, 8), (249, 115, 22)]
    )

    # 2. Floral Baby Shower (Approved)
    p2 = create_demo_image(
        "demo_baby_shower_pastel.jpg",
        "Floral Pastel Baby Shower Arch",
        "Baby Shower -> Floral Baby Shower",
        [(250, 245, 255), (244, 114, 182), (192, 132, 252), (251, 191, 36)]
    )

    # 3. Romantic Anniversary (Approved)
    p3 = create_demo_image(
        "demo_romantic_anniversary.jpg",
        "25th Silver Jubilee Romantic Arch",
        "Anniversary -> 25th Anniversary",
        [(30, 27, 75), (225, 29, 72), (244, 63, 94), (254, 205, 211)]
    )

    # 4. Duplicate Image of #1 (Tests duplicate detection)
    p4 = os.path.join(DEMO_DIR, "demo_duplicate_of_safari.jpg")
    img_orig = Image.open(p1)
    img_orig.save(p4)

    # 5. Severely Blurry Image (Tests quality blur detection)
    p5 = create_demo_image(
        "demo_blurry_unusable_decor.jpg",
        "Unusable Blurry Stage",
        "Quality Rejection Test",
        [(50, 50, 50), (100, 100, 100), (150, 150, 150)],
        blur=True
    )

    # 6. Welcome Baby Boy (Review required / Edge case)
    p6 = create_demo_image(
        "demo_welcome_baby_boy.jpg",
        "Welcome Baby Boy Organic Cloud",
        "Welcome Baby -> Baby Boy",
        [(239, 246, 255), (59, 130, 246), (147, 197, 253), (219, 234, 254)]
    )

    demo_files = [
        (p1, "demo_1st_birthday_safari.jpg"),
        (p2, "demo_baby_shower_pastel.jpg"),
        (p3, "demo_romantic_anniversary.jpg"),
        (p4, "demo_duplicate_of_safari.jpg"),
        (p5, "demo_blurry_unusable_decor.jpg"),
        (p6, "demo_welcome_baby_boy.jpg"),
    ]

    print("\nRunning images through the 5-step production pipeline...")
    processed_items = []
    for path, name in demo_files:
        item = processor.process_image(source_file_path=path, original_filename=name)
        processed_items.append(item)
        print(f" -> Processed '{name}' -> Status: {item.status} (Quality: {item.quality_status}, Blur Score: {item.blur_score:.1f}, IsDuplicate: {item.is_duplicate})")

    # Generate metadata and drive upload for approved items
    for item in processed_items:
        if item.status == "APPROVED":
            print(f"\nGenerating catalog metadata for approved item #{item.id}...")
            meta = meta_service.generate_for_image(item.id)
            if meta:
                print(f" -> Metadata generated: '{meta.name}'")

            print(f"Syncing item #{item.id} to Google Drive folder...")
            drive_res = drive_service.upload_approved_image(item.id)
            print(f" -> Google Drive Sync: {drive_res.get('message')}")

    db.close()
    print("\n[SUCCESS] Demo ingestion completed successfully into PostgreSQL!")


if __name__ == "__main__":
    seed_demo_pipeline()
