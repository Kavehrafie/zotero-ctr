from pathlib import Path
import tomllib
from pydantic import BaseModel, field_validator

CONFIG_PATH = Path("zotero-ctr.toml")


class Config(BaseModel):
    webdav_url: str
    webdav_username: str
    webdav_password: str
    storage_root: Path
    local_api_key: str = ""

    @field_validator("storage_root", mode="before")
    @classmethod
    def expand(cls, value):
        return Path(value).expanduser()


def load_config(path: Path = CONFIG_PATH) -> Config:
    return Config.model_validate(tomllib.loads(path.read_text()))


def save_config(path: Path, cfg: Config) -> None:
    lines = [f"{key} = {value!r}" for key, value in cfg.model_dump(mode="json").items()]
    path.write_text("\n".join(lines) + "\n")
