"""Language-specific dependency detection helpers."""
from __future__ import annotations

from typing import Any, Callable, Dict, Set

from . import node, os_pkgs, python

ReadContent = Callable[[Dict[str, Any]], str]


def detect_python_required(manifest: Dict[str, Any], read_content: ReadContent) -> Set[str]:
    return python.detect_required(manifest, read_content)


def detect_node_required(manifest: Dict[str, Any], read_content: ReadContent) -> Set[str]:
    return node.detect_required(manifest, read_content)


def extract_node_declared(manifest: Dict[str, Any], read_content: ReadContent) -> Set[str]:
    return node.extract_declared(manifest, read_content)


def detect_node_installs(dockerfile: str | None, build_command: str | None) -> Set[str]:
    return node.detect_installs(dockerfile, build_command)


def detect_os_packages(manifest: Dict[str, Any], read_content: ReadContent) -> Dict[str, Set[str]]:
    return os_pkgs.detect_os_packages(manifest, read_content)


__all__ = [
    "detect_python_required",
    "detect_node_required",
    "extract_node_declared",
    "detect_node_installs",
    "detect_os_packages",
]
