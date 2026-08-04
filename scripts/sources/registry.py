"""Stable adapter registry used by the command line runner and tests."""

from .appd_bg import AppdAdapter
from .hidmet_rs import HidmetAdapter
from .hydroinfo_hu import HydroinfoAdapter
from .pegelonline_de import PegelonlineAdapter
from .shmu_sk import ShmuAdapter
from .viadonau_at import ViaDonauAdapter
from .vodniputovi_hr import VodniputoviAdapter

ADAPTERS = {
    "de": PegelonlineAdapter,
    "at": ViaDonauAdapter,
    "sk": ShmuAdapter,
    "hu": HydroinfoAdapter,
    "hr": VodniputoviAdapter,
    "bg": AppdAdapter,
    "rs": HidmetAdapter,
}


def get_adapter(source: str):
    try:
        return ADAPTERS[source]()
    except KeyError as exc:
        raise ValueError(f"Unknown source {source!r}; choose from {', '.join(ADAPTERS)}") from exc
