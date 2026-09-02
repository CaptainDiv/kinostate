from .runway import RunwayAdapter
from .pika import PikaAdapter
from .luma import LumaAdapter
from .kling import KlingAdapter
from .kling_o1_reference import KlingO1ReferenceAdapter
from .seedance import SeedanceAdapter

ADAPTERS = {
    "runway": RunwayAdapter,
    "pika": PikaAdapter,
    "luma": LumaAdapter,
    "kling": KlingAdapter,
    "kling_o1_reference": KlingO1ReferenceAdapter,
    "seedance": SeedanceAdapter,
}

__all__ = [
    "RunwayAdapter",
    "PikaAdapter",
    "LumaAdapter",
    "KlingAdapter",
    "KlingO1ReferenceAdapter",
    "SeedanceAdapter",
    "ADAPTERS",
]
