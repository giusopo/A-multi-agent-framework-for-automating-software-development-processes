from typing import Dict, List


class Component:
    """
    Internal representation of a logical component.
    """

    def __init__(self, component_data: dict):
        self.id: str = component_data.get("id")
        self.responsibilities: List[str] = component_data.get("responsibilities", [])
        self.interfaces: Dict = component_data.get("interfaces", {})

    def __repr__(self):
        return f"Component(id={self.id})"

class Connector:
    """
    Internal representation of a relationship between components.
    """

    def __init__(self, connector_data: dict):
        self.source: str = connector_data.get("source") or connector_data.get("name")
        self.target: str = connector_data.get("target")
        self.type: str = connector_data.get("type")

    def __repr__(self):
        return f"Connector({self.source} -> {self.target})"

class ArchitectureModel:
    """
    Internal representation of a selected architecture.
    """

    def __init__(self, architecture_data: dict):
        self.id: str = architecture_data.get("architecture_id")
        self.name: str = architecture_data.get("name")
        self.views: Dict = architecture_data.get("views", {})

    def get_view_names(self) -> List[str]:
        return list(self.views.keys())

    def get_view(self, view_name: str) -> dict:
        return self.views.get(view_name, {})

    def get_logical_components(self) -> List[Component]:
        logical_view = self.views.get("logical_view", {})
        components_data = logical_view.get("components", [])
        return [Component(c) for c in components_data]
    
    def get_logical_connectors(self) -> List[Connector]:
        logical_view = self.views.get("logical_view", {})
        connectors_data = logical_view.get("connectors", [])
        return [Connector(c) for c in connectors_data]

    def to_dict(self) -> dict:
        return {
            "architecture_id": self.id,
            "architecture_name": self.name,
            "views": self.get_view_names(),
            "components": [c.id for c in self.get_logical_components()],
            "relationships": [
                {
                    "source": conn.source,
                    "target": conn.target,
                    "type": conn.type
                }
                for conn in self.get_logical_connectors()
            ]
        }
