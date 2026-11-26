from .base import Capability, CapabilityContext, CapabilityRegistry, UnknownCapability
from .pay_bill import PayBill
from .gas import BookGasCylinder
from .medicine import RefillMedicine
from .message import MessageChild


def default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for capability in (PayBill(), BookGasCylinder(), RefillMedicine(), MessageChild()):
        registry.register(capability)
    return registry


__all__ = [
    "Capability",
    "CapabilityContext",
    "CapabilityRegistry",
    "UnknownCapability",
    "default_registry",
]
