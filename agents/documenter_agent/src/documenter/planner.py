from typing import Dict, List
from src.documenter.models import ArchitectureModel


class DocumentationPlan:
    """
    Represents the documentation plan for a selected architecture.
    """

    def __init__(self, architecture_id: str, views: List[str]):
        self.architecture_id = architecture_id
        self.views = views

    def to_dict(self) -> Dict:
        return {
            "architecture_id": self.architecture_id,
            "views_to_document": self.views
        }


def create_documentation_plan(model: ArchitectureModel) -> DocumentationPlan:
    """
    Create a documentation plan based on available views.
    """
    available_views = model.get_view_names()

    # Simple deterministic rule (KB v0.1)
    views_to_document = []

    if "context_view" in available_views:
        views_to_document.append("context_view")

    if "logical_view" in available_views:
        views_to_document.append("logical_view")

    if "deployment_view" in available_views:
        views_to_document.append("deployment_view")

    if "runtime_view" in available_views:
        views_to_document.append("runtime_view")

    if "security_view" in available_views:
        views_to_document.append("security_view")

    return DocumentationPlan(model.id, views_to_document)