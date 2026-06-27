from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "outputs"))
    resource_dir: Path = Path(os.getenv("RESOURCE_DIR", "resources"))
    template_dir: Path = Path(os.getenv("TEMPLATE_DIR", "resources/templates"))


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
settings.resource_dir.mkdir(parents=True, exist_ok=True)
settings.template_dir.mkdir(parents=True, exist_ok=True)
