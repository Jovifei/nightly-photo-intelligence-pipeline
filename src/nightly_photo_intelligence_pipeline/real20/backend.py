"""Load exactly the verified weight bytes through a native bound handle."""

from io import BytesIO
from pathlib import Path
from typing import Any

from ..engineering.common import sha256
from ..n2b2_synthetic.torchvision_loader import RealTorchVisionBackend
from ..windows_bound_promotion import bind_existing_directory
from .contracts import Real20Error


class BoundTorchVisionBackend(RealTorchVisionBackend):
    def _load_state_dict(self, torch: Any, path: Path) -> Any:
        with (
            bind_existing_directory(path.parent, writable=False) as parent,
            parent.open_file(path.name) as file,
        ):
            data = file.read_all(max_bytes=300 * 1024 * 1024)
        if sha256(data) != path.parent.name or path.parent.name not in self._subdirs.values():
            raise Real20Error("REAL20_MODEL_BYTES_CHANGED")
        return torch.load(BytesIO(data), map_location="cpu", weights_only=True)
