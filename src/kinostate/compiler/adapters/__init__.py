from .runway import RunwayAdapter
from .pika import PikaAdapter
from .luma import LumaAdapter
from .kling import KlingAdapter
from .kling_o1_reference import KlingO1ReferenceAdapter
from .seedance import SeedanceAdapter
from .minimax_h3 import MinimaxH3Adapter
from .xai_grok_imagine_video import XaiGrokImagineVideoAdapter
from .gemini_omni_flash import GeminiOmniFlashAdapter

ADAPTERS = {
    "runway": RunwayAdapter,
    "pika": PikaAdapter,
    "luma": LumaAdapter,
    "kling": KlingAdapter,
    "kling_o1_reference": KlingO1ReferenceAdapter,
    "seedance": SeedanceAdapter,
    "minimax_h3": MinimaxH3Adapter,
    "xai_grok_imagine_video": XaiGrokImagineVideoAdapter,
    "gemini_omni_flash": GeminiOmniFlashAdapter,
}

__all__ = [
    "RunwayAdapter",
    "PikaAdapter",
    "LumaAdapter",
    "KlingAdapter",
    "KlingO1ReferenceAdapter",
    "SeedanceAdapter",
    "MinimaxH3Adapter",
    "XaiGrokImagineVideoAdapter",
    "GeminiOmniFlashAdapter",
    "ADAPTERS",
]
