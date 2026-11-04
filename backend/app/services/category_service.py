import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.category_repo import CategoryRepository
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryTreeNode, CategoryResponse

logger = logging.getLogger("eventdhara.category_service")

# Initial canonical category tree specified in project requirements
INITIAL_CATEGORIES_DATA = {
    "Wedding Decoration": [
        "Mandap Decoration",
        "Stage Decoration",
        "Entry Gate",
        "Varmala Stage",
        "Floral Wedding Decor"
    ],
    "Birthday Decoration": [
        "1st Birthday",
        "Romantic Birthday",
        "Surprise",
        "Rooftop",
        "Boys",
        "Girls",
        "Simple Balloon",
        "Butterfly Theme",
        "Cartoon Theme",
        "Cocomelon Theme",
        "Jungle Theme",
        "Pastel Theme",
        "Mickey Mouse Theme",
        "Superhero Theme",
        "Unicorn Theme"
    ],
    "Engagement Decoration": [
        "Floral Ring Backdrop",
        "Pastel Theme",
        "Romantic Ring Ceremony"
    ],
    "Haldi Decoration": [
        "Yellow Marigold Setup",
        "Haldi Floral Urli",
        "Traditional Yellow Backdrop"
    ],
    "Mehndi Decoration": [
        "Boho Mehndi Setup",
        "Colorful Drapes",
        "Floral Jhula Mehndi"
    ],
    "Reception Decoration": [
        "Luxury Stage Setup",
        "Candlelight Pathway",
        "Grand Backdrop"
    ],
    "Stage Decoration": [
        "Floral Backdrop Stage",
        "Geometric LED Stage",
        "Royal Theme Stage"
    ],
    "Mandap Decoration": [
        "Dome Mandap",
        "Floral Pillar Mandap",
        "Open Air Mandap"
    ],
    "Corporate Events": [
        "Conference Backdrop",
        "Annual Gala Stage",
        "Product Launch Setup"
    ],
    "Baby Shower": [
        "Floral Baby Shower",
        "Pastel Color",
        "Mom To Be",
        "Real Flower Decor"
    ],
    "Anniversary": [
        "1st Anniversary",
        "25th Anniversary",
        "50th Anniversary",
        "Romantic Decor"
    ],
    "Welcome Baby": [
        "Baby Boy",
        "Baby Girl",
        "Floral Decor"
    ],
    "Other": [
        "General Celebration",
        "Custom Setup"
    ]
}


class CategoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CategoryRepository(db)

    def seed_initial_categories(self):
        """Seed the canonical categories required by specification if not already present."""
        try:
            for parent_name, subcategories in INITIAL_CATEGORIES_DATA.items():
                parent = self.repo.get_by_slug(CategoryRepository(self.db).get_by_slug(parent_name.lower().replace(" ", "-")) and "")
                # Search by exact name
                existing_parent = (
                    self.db.query(Category)
                    .filter(Category.name.ilike(parent_name), Category.parent_id == None)
                    .first()
                )
                if not existing_parent:
                    existing_parent = self.repo.create(CategoryCreate(
                        name=parent_name,
                        description=f"Curated collection for {parent_name} setups and designs.",
                        parent_id=None
                    ))
                    logger.info("Created root category: %s", parent_name)

                # Seed subcategories
                for sub_name in subcategories:
                    existing_sub = (
                        self.db.query(Category)
                        .filter(Category.name.ilike(sub_name), Category.parent_id == existing_parent.id)
                        .first()
                    )
                    if not existing_sub:
                        self.repo.create(CategoryCreate(
                            name=sub_name,
                            description=f"{sub_name} theme decoration",
                            parent_id=existing_parent.id
                        ))
        except Exception as e:
            logger.error("Error seeding initial categories: %s", e)
            self.db.rollback()

    def get_category_tree(self, active_only: bool = False) -> List[CategoryTreeNode]:
        all_categories = self.repo.get_all(active_only=active_only)
        image_counts = self.repo.get_image_counts()

        # Build mapping
        cat_map: Dict[int, CategoryTreeNode] = {}
        for cat in all_categories:
            count = image_counts.get(cat.id, 0)
            cat_map[cat.id] = CategoryTreeNode(
                id=cat.id,
                name=cat.name,
                slug=cat.slug,
                description=cat.description,
                parent_id=cat.parent_id,
                is_active=cat.is_active,
                image_count=count,
                depth=0,
                children=[]
            )

        root_nodes: List[CategoryTreeNode] = []

        def assign_depth(node: CategoryTreeNode, current_depth: int):
            node.depth = current_depth
            for ch in node.children:
                assign_depth(ch, current_depth + 1)

        # Build tree structure
        for cat in all_categories:
            node = cat_map[cat.id]
            if cat.parent_id and cat.parent_id in cat_map:
                cat_map[cat.parent_id].children.append(node)
            else:
                root_nodes.append(node)

        # Assign depths
        for root in root_nodes:
            assign_depth(root, 0)

        # Compute cumulative image counts for parents
        def compute_cumulative_count(node: CategoryTreeNode) -> int:
            total = node.image_count
            for child in node.children:
                total += compute_cumulative_count(child)
            node.image_count = total
            return total

        for root in root_nodes:
            compute_cumulative_count(root)

        return root_nodes

    def get_category_breadcrumbs(self, category_id: int) -> List[Dict[str, Any]]:
        breadcrumbs = []
        curr = self.repo.get_by_id(category_id)
        visited = set()
        while curr and curr.id not in visited:
            visited.add(curr.id)
            breadcrumbs.insert(0, {"id": curr.id, "name": curr.name, "slug": curr.slug})
            if curr.parent_id:
                curr = self.repo.get_by_id(curr.parent_id)
            else:
                break
        return breadcrumbs

    def get_category_details(self, category_id: int) -> Optional[Dict[str, Any]]:
        cat = self.repo.get_by_id(category_id)
        if not cat:
            return None
        breadcrumbs = self.get_category_breadcrumbs(category_id)
        image_counts = self.repo.get_image_counts()
        children = self.repo.get_children(category_id)

        return {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "parent_id": cat.parent_id,
            "is_active": cat.is_active,
            "created_at": cat.created_at,
            "updated_at": cat.updated_at,
            "image_count": image_counts.get(cat.id, 0),
            "breadcrumbs": breadcrumbs,
            "children_count": len(children),
            "children": [
                {
                    "id": c.id,
                    "name": c.name,
                    "slug": c.slug,
                    "image_count": image_counts.get(c.id, 0),
                    "is_active": c.is_active,
                }
                for c in children
            ],
        }
