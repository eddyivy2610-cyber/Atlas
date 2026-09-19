"""Unit tests for PlantUML and Mermaid text parsers."""

from umldoc.parser.puml_parser import PlantUMLParser
from umldoc.parser.mermaid_parser import MermaidParser
from umldoc.ir.base import ElementKind, MemberVisibility, RelationType
from umldoc.ir.dynamic_model import InteractionEventType


SAMPLE_PUML_CLASS = """
@startuml
class "Order" as pkg.Order <<dataclass>> {
  +id: str
  -total_price: float = 0.0
  +calculate_tax(rate: float): float
  #{static} validate_id(id: str): bool
}
class "Customer" as pkg.Customer {
  +name: str
}
pkg.Customer <|-- pkg.Order : extends
pkg.Order *-- pkg.Customer : owns
@enduml
"""

SAMPLE_PUML_SEQ = """
@startuml
autonumber
participant "Client" as Client
participant "order_svc: OrderService" as OrderService
Client -> OrderService : place_order(item="Laptop", qty=1)
OrderService --> Client : return True
@enduml
"""

SAMPLE_MMD_CLASS = """
classDiagram
    class UserProfile {
        <<dataclass>>
        +str user_id
        +str email
        +get_profile(id) str
    }
    class StorageBackend {
        <<interface>>
        +save(key, payload) bool
    }
    StorageBackend <|-- UserProfile : implements
"""

SAMPLE_MMD_SEQ = """
sequenceDiagram
    autonumber
    participant Client as "Client"
    participant Svc as "UserService"
    Client->>+Svc: register_user(id="u1")
    Svc-->>-Client: return None
"""


def test_plantuml_class_parser():
    """Verify PlantUML class diagram parsing into StaticModelIR."""
    model = PlantUMLParser.parse_class_diagram(SAMPLE_PUML_CLASS, project_name="OrderApp")
    assert model.project_name == "OrderApp"
    assert len(model.classes) == 2

    class_map = {c.name: c for c in model.classes}
    assert "Order" in class_map
    order_cls = class_map["Order"]
    assert order_cls.kind == ElementKind.DATACLASS
    assert len(order_cls.attributes) == 2
    assert len(order_cls.methods) == 2

    # Check method details
    calc_m = next(m for m in order_cls.methods if m.name == "calculate_tax")
    assert calc_m.visibility == MemberVisibility.PUBLIC
    assert len(calc_m.parameters) == 1
    assert calc_m.parameters[0].name == "rate"
    assert calc_m.parameters[0].type_annotation == "float"

    # Check relations
    assert len(model.relations) == 2
    rel_types = [r.relation_type for r in model.relations]
    assert RelationType.INHERITANCE in rel_types
    assert RelationType.COMPOSITION in rel_types


def test_plantuml_sequence_parser():
    """Verify PlantUML sequence diagram parsing into TraceSessionIR."""
    session = PlantUMLParser.parse_sequence_diagram(SAMPLE_PUML_SEQ, scenario_name="OrderScenario")
    assert session.scenario_name == "OrderScenario"
    assert len(session.participants) == 2
    assert len(session.interactions) == 2

    evt1 = session.interactions[0]
    assert evt1.event_type == InteractionEventType.CALL
    assert evt1.caller_id == "Client"
    assert evt1.callee_id == "OrderService"
    assert evt1.method_name == "place_order"
    assert "item" in evt1.arguments
    assert evt1.arguments["item"].repr_value == '"Laptop"'


def test_mermaid_class_parser():
    """Verify Mermaid classDiagram parsing into StaticModelIR."""
    model = MermaidParser.parse_class_diagram(SAMPLE_MMD_CLASS, project_name="UserApp")
    assert len(model.classes) == 2

    class_map = {c.name: c for c in model.classes}
    user_cls = class_map["UserProfile"]
    assert user_cls.kind == ElementKind.DATACLASS
    assert len(user_cls.attributes) == 2

    storage_cls = class_map["StorageBackend"]
    assert storage_cls.kind == ElementKind.INTERFACE
    assert storage_cls.is_abstract is True


def test_mermaid_sequence_parser():
    """Verify Mermaid sequenceDiagram parsing into TraceSessionIR."""
    session = MermaidParser.parse_sequence_diagram(SAMPLE_MMD_SEQ, scenario_name="UserSeq")
    assert len(session.participants) == 2
    assert len(session.interactions) == 2
    assert session.interactions[0].method_name == "register_user"
