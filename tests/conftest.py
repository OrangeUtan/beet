import json
from pathlib import Path

from pytest_insta import Fmt

from beet import DataPack, ProjectConfig, ResourcePack
from beet.core.utils import dump_json


class FmtResourcePack(Fmt[ResourcePack]):
    extension = ".resource_pack"

    def load(self, path: Path) -> ResourcePack:
        return ResourcePack(path=next(path.iterdir()))

    def dump(self, path: Path, value: ResourcePack):
        value.save(path, overwrite=True)


class FmtDataPack(Fmt[DataPack]):
    extension = ".data_pack"

    def load(self, path: Path) -> DataPack:
        return DataPack(path=next(path.iterdir()))

    def dump(self, path: Path, value: DataPack):
        value.save(path, overwrite=True)


class FmtConfig(Fmt[ProjectConfig]):
    extension = ".beet-config"

    def load(self, path: Path) -> ProjectConfig:
        config = ProjectConfig(**json.loads(path.read_text()))
        self.fix_paths(config)
        return config

    def dump(self, path: Path, value: ProjectConfig):
        path.write_text(dump_json(value.dict()))

    def fix_paths(self, config: ProjectConfig):
        if config.directory:
            config.directory = str(Path(config.directory))
        if config.output:
            config.output = str(Path(config.output))

        config.data_pack.load = [str(Path(p)) for p in config.data_pack.load]
        config.resource_pack.load = [str(Path(p)) for p in config.resource_pack.load]
        config.templates = [str(Path(p)) for p in config.templates]

        for entry in config.pipeline:
            if isinstance(entry, ProjectConfig):
                self.fix_paths(entry)
