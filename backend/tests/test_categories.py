import pytest
from app.core.database import SessionLocal
from app.services.category_service import CategoryService
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryCreate


def test_canonical_categories_seeded():
    db = SessionLocal()
    service = CategoryService(db)
    service.seed_initial_categories()
    
    repo = CategoryRepository(db)
    roots = repo.get_root_categories()
    root_names = [r.name for r in roots]
    
    assert "Birthday Decoration" in root_names
    assert "Baby Shower" in root_names
    assert "Anniversary" in root_names
    assert "Welcome Baby" in root_names
    db.close()


def test_category_tree_hierarchy():
    db = SessionLocal()
    service = CategoryService(db)
    tree = service.get_category_tree()
    
    assert len(tree) >= 4
    birthday_node = next((n for n in tree if n.name == "Birthday Decoration"), None)
    assert birthday_node is not None
    assert len(birthday_node.children) >= 15
    db.close()


def test_category_crud_operations():
    db = SessionLocal()
    repo = CategoryRepository(db)
    
    # Create test category
    created = repo.create(CategoryCreate(
        name="Test Festivity Suite",
        description="Temporary testing category"
    ))
    assert created.id is not None
    assert created.slug.startswith("test-festivity-suite")
    
    # Delete test category
    deleted = repo.delete(created.id)
    assert deleted is True
    db.close()
