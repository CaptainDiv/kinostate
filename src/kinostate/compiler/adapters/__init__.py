from .runway import RunwayAdapter
from .pika import PikaAdapter
from .luma import LumaAdapter
from .kling import KlingAdapter

ADAPTERS = {
    "runway": RunwayAdapter,
    "pika": PikaAdapter,
    "luma": LumaAdapter,
    "kling": KlingAdapter,
}

__all__ = ["RunwayAdapter", "PikaAdapter", "LumaAdapter", "KlingAdapter", "ADAPTERS"]
