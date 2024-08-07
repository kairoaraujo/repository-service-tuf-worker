# SPDX-FileCopyrightText: 2023 Repository Service for TUF Contributors
# SPDX-FileCopyrightText: 2022-2023 VMware Inc
#
# SPDX-License-Identifier: MIT
import importlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

from dynaconf import Dynaconf
from tuf.api.metadata import Metadata, T


@dataclass
class ServiceSettings:
    """Dataclass for service settings."""

    names: List[str]
    required: bool
    default: Optional[Any] = None


class IStorage(ABC):
    @classmethod
    @abstractmethod
    def configure(cls, settings: Dynaconf) -> "IStorage":
        """
        Run actions to verify, configure and create object using the settings.
        """
        raise NotImplementedError  # pragma: no cover

    @classmethod
    def from_dynaconf(cls, settings: Dynaconf) -> None:
        """
        Run actions to verify and configure using the dynaconf settings.
        """
        _setup_service_dynaconf(cls, settings.STORAGE_BACKEND, settings)

    @classmethod
    @abstractmethod
    def settings(cls) -> List[ServiceSettings]:
        """
        Define all the ServiceSettings required in settings.
        """

        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def get(self, rolename: str, version: Optional[int]) -> Metadata[T]:
        """
        Return metadata from specific role name, optionally specific version
        (latest if None).
        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def put(
        self,
        file_data: bytes,
        filename: str,
    ) -> None:
        """
        Stores file bytes within a file with a specific filename.
        """
        raise NotImplementedError  # pragma: no cover


def _setup_service_dynaconf(cls: Any, backend: Any, settings: Dynaconf):
    """
    Setup a Interface Service (IService) from settings Dynaconf (environment
    variables)
    """
    # the 'service import is used to retrieve sublcasses (Implemented Services)
    from repository_service_tuf_worker import services  # noqa

    service_backends = [i.__name__.upper() for i in cls.__subclasses__()]
    backend_name = f"RSTUF_{cls.__name__.replace('I', '').upper()}_BACKEND"

    if type(backend) is not str and issubclass(
        backend, tuple(cls.__subclasses__())
    ):
        logging.debug(f"{backend_name} is defined as {backend}")

    elif backend.upper() not in service_backends:
        raise ValueError(
            f"Invalid {backend_name} {backend}. "
            f"Supported {backend_name} {', '.join(service_backends)}"
        )
    else:
        backend = getattr(
            importlib.import_module("repository_service_tuf_worker.services"),
            backend,
        )
        # look all required settings
        if missing_settings := [
            s.names
            for s in backend.settings()
            if s.required and all(n not in settings for n in s.names)
        ]:
            # add the prefix `RSTUF_` to attributes including as dynaconf
            # removes it. It makes the message more clear to the user.
            missing_stg: List = []
            for missing in missing_settings:
                missing_stg.append("RSTUF_" + " or RSTUF_".join(missing))

            raise AttributeError(
                "'Settings' object has no attribute(s) (environment variables)"
                f": {', '.join(missing_stg)}"
            )

        # Make sure all settings have value set for at least one of their names
        for s_var in backend.settings():
            if all(
                [
                    settings.store.get(var_name) is None
                    for var_name in s_var.names
                ]
            ):
                for var_name in s_var.names:
                    settings.store[var_name] = s_var.default

        if cls.__name__ == "IStorage":
            settings.STORAGE_BACKEND = backend
            settings.STORAGE = settings.STORAGE_BACKEND.configure(settings)

        else:
            raise ValueError(f"Invalid Interface {cls.__name__}")
