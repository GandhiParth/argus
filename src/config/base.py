from dataclasses import dataclass, field
from pathlib import Path

from conf import BASE_PATH


@dataclass(frozen=True)
class StorageConfig:
    base_dir: Path = field(default_factory=lambda: Path(BASE_PATH).resolve())

    def store_root(self, *subpaths: str, create: bool = True) -> Path:
        path = self.base_dir / "store"
        if subpaths:
            path = path.joinpath(*subpaths)

        if create:
            path.mkdir(parents=True, exist_ok=True)

        return path

    def tmp_root(self, *subpaths: str, create: bool = True) -> Path:
        path = self.base_dir / "tmp"
        if subpaths:
            path = path.joinpath(*subpaths)

        if create:
            path.mkdir(parents=True, exist_ok=True)

        return path
