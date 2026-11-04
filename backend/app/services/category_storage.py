import os
import re
import shutil
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.category import Category
from app.models.image import ImageItem

logger = logging.getLogger("eventdhara.category_storage")

CATEGORY_FOLDER_MAPPING = {
    "wedding": "Wedding",
    "birthday": "Birthday",
    "engagement": "Engagement",
    "haldi": "Haldi",
    "mehndi": "Mehndi",
    "mehendi": "Mehndi",
    "reception": "Reception",
    "stage": "Stage",
    "mandap": "Mandap",
    "corporate": "Corporate",
    "baby shower": "Baby_Shower",
    "anniversary": "Anniversary",
    "welcome baby": "Welcome_Baby",
}

STATUS_FOLDER_MAPPING = {
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
    "REVIEW_REQUIRED": "Review_Required",
    "DUPLICATE": "Duplicates",
    "PENDING": "Review_Required"
}


def get_canonical_category_name(category: Optional[Category]) -> str:
    """Finds root category and returns standardized folder name."""
    if not category:
        return "Other"

    # Walk up to the root parent
    curr = category
    visited = set()
    while curr.parent and curr.id not in visited:
        visited.add(curr.id)
        curr = curr.parent

    root_name = curr.name.lower()
    for key, folder_name in CATEGORY_FOLDER_MAPPING.items():
        if key in root_name:
            return folder_name

    # If not matched in dictionary, sanitize root name
    clean = re.sub(r"[^\w\s-]", "", curr.name).strip()
    return clean.replace(" ", "_") or "Other"


def get_category_folder_from_name(category_name: Optional[str]) -> str:
    """Maps arbitrary category string to standardized folder name."""
    if not category_name:
        return "Other"
    lower = category_name.lower()
    for key, folder in CATEGORY_FOLDER_MAPPING.items():
        if key in lower:
            return folder
    clean = re.sub(r"[^\w\s-]", "", category_name).strip()
    return clean.replace(" ", "_") or "Other"


def get_status_folder_name(status: str) -> str:
    return STATUS_FOLDER_MAPPING.get(status.upper(), "Review_Required")


def get_category_storage_dir(category_folder: str, status_folder: str) -> str:
    """Returns absolute path to storage/EventDhara/{Category}/{Status}."""
    dir_path = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "EventDhara", category_folder, status_folder))
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def get_safe_destination_path(target_dir: str, original_filename: str, file_uuid: str) -> str:
    """
    Preserves original filename. If already exists in target_dir,
    creates non-colliding name without overwriting.
    """
    clean_filename = os.path.basename(original_filename).replace("..", "").replace("/", "").replace("\\", "")
    if not clean_filename:
        clean_filename = f"{file_uuid}.jpg"

    base_name, ext = os.path.splitext(clean_filename)
    if not ext:
        ext = ".jpg"

    target_path = os.path.join(target_dir, f"{base_name}{ext}")
    if not os.path.exists(target_path):
        return target_path

    # Handle collision safely: append uuid prefix
    safe_name = f"{base_name}_{file_uuid[:8]}{ext}"
    return os.path.join(target_dir, safe_name)


def organize_image_in_category_folder(
    image: ImageItem,
    old_status: Optional[str] = None,
    old_category_folder: Optional[str] = None
) -> Tuple[str, str]:
    """
    Synchronizes an ImageItem into its category folder:
    storage/EventDhara/{Category}/{Status}/{filename}
    Returns (absolute_file_path, relative_storage_path).
    """
    cat_folder = get_canonical_category_name(image.category)
    status_folder = get_status_folder_name(image.status)
    target_dir = get_category_storage_dir(cat_folder, status_folder)

    dest_path = get_safe_destination_path(target_dir, image.original_filename, image.uuid)

    # Source file: either existing file_path or from storage/processed
    source_path = image.file_path
    if not os.path.exists(source_path):
        alt = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "processed", image.filename))
        if os.path.exists(alt):
            source_path = alt

    if os.path.exists(source_path):
        try:
            # If changing status or category, clean up previous copy in old location
            if old_status and old_status != image.status:
                old_status_folder = get_status_folder_name(old_status)
                old_cat = old_category_folder or cat_folder
                old_dir = os.path.abspath(os.path.join(settings.STORAGE_ROOT, "EventDhara", old_cat, old_status_folder))
                # Search for any file in old_dir that belongs to this uuid or original filename
                if os.path.exists(old_dir):
                    for fname in os.listdir(old_dir):
                        if image.uuid[:8] in fname or fname == image.original_filename:
                            old_file = os.path.join(old_dir, fname)
                            if os.path.exists(old_file) and old_file != source_path:
                                try:
                                    os.remove(old_file)
                                except Exception:
                                    pass

            shutil.copy2(source_path, dest_path)
            # Relative path from project root
            rel_path = os.path.relpath(dest_path, settings.STORAGE_ROOT).replace("\\", "/")
            return dest_path, f"storage/{rel_path}"
        except Exception as e:
            logger.warning("Failed copying to category folder: %s", e)

    return image.file_path, image.storage_path


def remove_image_from_storage(image: ImageItem):
    """Safely removes image files from category and processed storage when deleted."""
    # 1. Remove from category folders
    cat_folder = get_canonical_category_name(image.category)
    for st in ["Approved", "Rejected", "Review_Required", "Duplicates"]:
        folder = os.path.join(settings.STORAGE_ROOT, "EventDhara", cat_folder, st)
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                if image.uuid[:8] in fname or fname == image.original_filename:
                    fpath = os.path.join(folder, fname)
                    if os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                            logger.info("Removed category file: %s", fpath)
                        except Exception as e:
                            logger.warning("Error removing %s: %s", fpath, e)

    # 2. Remove from processed storage
    if image.file_path and os.path.exists(image.file_path):
        try:
            os.remove(image.file_path)
        except Exception:
            pass

    proc_file = os.path.join(settings.STORAGE_ROOT, "processed", image.filename)
    if os.path.exists(proc_file):
        try:
            os.remove(proc_file)
        except Exception:
            pass
