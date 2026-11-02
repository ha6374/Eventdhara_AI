import re
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.category import Category
from app.models.image import ImageItem
from app.schemas.category import CategoryCreate, CategoryUpdate


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, category_id: int) -> Optional[Category]:
        return self.db.query(Category).filter(Category.id == category_id).first()

    def get_by_slug(self, slug: str) -> Optional[Category]:
        return self.db.query(Category).filter(Category.slug == slug).first()

    def get_all(self, active_only: bool = False, search: Optional[str] = None) -> List[Category]:
        query = self.db.query(Category)
        if active_only:
            query = query.filter(Category.is_active == True)
        if search:
            query = query.filter(Category.name.ilike(f"%{search}%"))
        return query.order_by(Category.name.asc()).all()

    def get_root_categories(self, active_only: bool = False) -> List[Category]:
        query = self.db.query(Category).filter(Category.parent_id == None)
        if active_only:
            query = query.filter(Category.is_active == True)
        return query.order_by(Category.name.asc()).all()

    def get_children(self, parent_id: int, active_only: bool = False) -> List[Category]:
        query = self.db.query(Category).filter(Category.parent_id == parent_id)
        if active_only:
            query = query.filter(Category.is_active == True)
        return query.order_by(Category.name.asc()).all()

    def get_image_counts(self) -> dict:
        results = (
            self.db.query(ImageItem.category_id, func.count(ImageItem.id))
            .filter(ImageItem.category_id != None)
            .group_by(ImageItem.category_id)
            .all()
        )
        return {cat_id: count for cat_id, count in results}

    def create(self, obj_in: CategoryCreate) -> Category:
        slug = obj_in.slug or slugify(obj_in.name)
        # Check uniqueness
        base_slug = slug
        counter = 1
        while self.get_by_slug(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        db_obj = Category(
            name=obj_in.name.strip(),
            slug=slug,
            description=obj_in.description,
            parent_id=obj_in.parent_id,
            is_active=obj_in.is_active
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, db_obj: Category, obj_in: CategoryUpdate) -> Category:
        update_data = obj_in.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"]:
            update_data["name"] = update_data["name"].strip()
            if "slug" not in update_data or not update_data["slug"]:
                new_slug = slugify(update_data["name"])
                if new_slug != db_obj.slug:
                    # check uniqueness
                    base_slug = new_slug
                    counter = 1
                    while self.db.query(Category).filter(Category.slug == new_slug, Category.id != db_obj.id).first():
                        new_slug = f"{base_slug}-{counter}"
                        counter += 1
                    update_data["slug"] = new_slug

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, category_id: int) -> bool:
        category = self.get_by_id(category_id)
        if not category:
            return False
        self.db.delete(category)
        self.db.commit()
        return True
