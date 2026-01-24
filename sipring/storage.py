"""JSON file storage with file locking for NFS safety."""

import fcntl
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from .config import get_settings
from .models import RingConfig, RingConfigCreate, RingConfigUpdate

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Storage operation error."""
    pass


class ConfigNotFoundError(StorageError):
    """Configuration not found."""
    pass


class ConfigStorage:
    """JSON file storage for ring configurations."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or get_settings().config_file

    def _ensure_dir(self) -> None:
        """Ensure data directory exists."""
        dir_path = os.path.dirname(self.file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    @contextmanager
    def _locked_file(self, mode: str = 'r'):
        """Context manager for file operations with locking."""
        self._ensure_dir()

        # Create file if it doesn't exist
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"configs": []}, f)

        lock_type = fcntl.LOCK_EX if 'w' in mode or 'a' in mode else fcntl.LOCK_SH

        with open(self.file_path, mode) as f:
            try:
                fcntl.flock(f.fileno(), lock_type)
                yield f
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _read_data(self) -> dict:
        """Read and parse JSON data."""
        try:
            with self._locked_file('r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in config file, resetting")
            return {"configs": []}

    def _write_data(self, data: dict) -> None:
        """Write JSON data to file."""
        with self._locked_file('w') as f:
            json.dump(data, f, indent=2, default=str)

    def _config_from_dict(self, data: dict) -> RingConfig:
        """Convert dict to RingConfig with proper type handling."""
        # Parse datetime fields
        for field in ['created_at', 'last_ring_at']:
            if data.get(field) and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])

        # Parse UUID
        if 'id' in data and isinstance(data['id'], str):
            data['id'] = UUID(data['id'])

        return RingConfig(**data)

    def list_configs(self) -> list[RingConfig]:
        """List all configurations."""
        data = self._read_data()
        return [self._config_from_dict(c) for c in data.get("configs", [])]

    def get_config(self, id_or_slug: str) -> RingConfig:
        """Get configuration by UUID or slug."""
        configs = self.list_configs()

        # Try UUID first
        try:
            target_id = UUID(id_or_slug)
            for config in configs:
                if config.id == target_id:
                    return config
        except ValueError:
            pass  # Not a UUID, try slug

        # Try slug
        for config in configs:
            if config.slug == id_or_slug:
                return config

        raise ConfigNotFoundError(f"Config not found: {id_or_slug}")

    def create_config(self, config_data: RingConfigCreate) -> RingConfig:
        """Create a new configuration."""
        from .models import slugify

        data = self._read_data()
        configs = data.get("configs", [])

        # Generate slug if not provided
        new_slug = config_data.slug or slugify(config_data.name)

        # Check for slug uniqueness
        for existing in configs:
            if existing.get('slug') == new_slug:
                raise StorageError(f"Slug already exists: {new_slug}")

        # Create new config - exclude slug from dump and pass it separately
        config_dict = config_data.model_dump(exclude={'slug'})
        config = RingConfig(**config_dict, slug=new_slug)

        configs.append(config.model_dump(mode='json'))
        data["configs"] = configs
        self._write_data(data)

        logger.info(f"Created config: {config.id} ({config.name})")
        return config

    def update_config(self, id_or_slug: str, update_data: RingConfigUpdate) -> RingConfig:
        """Update an existing configuration."""
        data = self._read_data()
        configs = data.get("configs", [])

        # Find config
        config_idx = None
        target_id = None

        try:
            target_id = UUID(id_or_slug)
        except ValueError:
            pass

        for idx, c in enumerate(configs):
            c_id = UUID(c['id']) if isinstance(c['id'], str) else c['id']
            if (target_id and c_id == target_id) or c.get('slug') == id_or_slug:
                config_idx = idx
                break

        if config_idx is None:
            raise ConfigNotFoundError(f"Config not found: {id_or_slug}")

        # Apply updates
        existing = configs[config_idx]
        update_dict = update_data.model_dump(exclude_unset=True)

        # Check slug uniqueness if changing
        if 'slug' in update_dict and update_dict['slug'] != existing.get('slug'):
            for i, c in enumerate(configs):
                if i != config_idx and c.get('slug') == update_dict['slug']:
                    raise StorageError(f"Slug already exists: {update_dict['slug']}")

        existing.update(update_dict)
        configs[config_idx] = existing
        data["configs"] = configs
        self._write_data(data)

        logger.info(f"Updated config: {existing['id']}")
        return self._config_from_dict(existing)

    def delete_config(self, id_or_slug: str) -> None:
        """Delete a configuration."""
        data = self._read_data()
        configs = data.get("configs", [])

        target_id = None
        try:
            target_id = UUID(id_or_slug)
        except ValueError:
            pass

        new_configs = []
        found = False

        for c in configs:
            c_id = UUID(c['id']) if isinstance(c['id'], str) else c['id']
            if (target_id and c_id == target_id) or c.get('slug') == id_or_slug:
                found = True
                logger.info(f"Deleted config: {c['id']}")
            else:
                new_configs.append(c)

        if not found:
            raise ConfigNotFoundError(f"Config not found: {id_or_slug}")

        data["configs"] = new_configs
        self._write_data(data)

    def update_ring_status(
        self,
        id_or_slug: str,
        status: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Update last ring status for a configuration."""
        data = self._read_data()
        configs = data.get("configs", [])

        target_id = None
        try:
            target_id = UUID(id_or_slug)
        except ValueError:
            pass

        for c in configs:
            c_id = UUID(c['id']) if isinstance(c['id'], str) else c['id']
            if (target_id and c_id == target_id) or c.get('slug') == id_or_slug:
                c['last_ring_at'] = (timestamp or datetime.now(timezone.utc)).isoformat()
                c['last_ring_status'] = status
                break

        data["configs"] = configs
        self._write_data(data)


# Global storage instance
_storage: Optional[ConfigStorage] = None


def get_storage() -> ConfigStorage:
    """Get storage instance."""
    global _storage
    if _storage is None:
        _storage = ConfigStorage()
    return _storage
