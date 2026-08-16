"""Typed host-policy and result records for P5-WP03 archive security."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SIGNATURE_SUITE = "BMAS-SIG-1-ED25519"
CONFIDENTIALITY_SUITE = "BMAS-ENC-1-HPKE-X25519-HKDF-SHA256-AES256GCM"

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}")
_KEY_ID = re.compile(r"(?:ed25519|x25519):[0-9a-f]{64}")
_REPLAY_BINDING = re.compile(r"[0-9a-f]{64}")


class ArchiveSecurityStatus(StrEnum):
    """Stable actionable categories that never include secret-bearing detail."""

    LEGACY_POLICY_REQUIRED = "LEGACY_POLICY_REQUIRED"
    MALFORMED_ENVELOPE = "MALFORMED_ENVELOPE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"
    UNKNOWN_SIGNER = "UNKNOWN_SIGNER"
    SIGNER_KEY_MISMATCH = "SIGNER_KEY_MISMATCH"
    REVOKED_SIGNER = "REVOKED_SIGNER"
    SIGNER_NOT_YET_VALID = "SIGNER_NOT_YET_VALID"
    EXPIRED_SIGNER = "EXPIRED_SIGNER"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    REPLAY_REJECTED = "REPLAY_REJECTED"
    CONFIDENTIALITY_REQUIRED = "CONFIDENTIALITY_REQUIRED"
    DECRYPTION_KEY_REQUIRED = "DECRYPTION_KEY_REQUIRED"
    RECIPIENT_MISMATCH = "RECIPIENT_MISMATCH"
    DECRYPTION_FAILED = "DECRYPTION_FAILED"
    SECRET_MATERIAL_REJECTED = "SECRET_MATERIAL_REJECTED"


class ArchiveSecurityError(ValueError):
    """Fail-closed archive-security error with a stable non-secret category."""

    def __init__(self, status: ArchiveSecurityStatus, message: str) -> None:
        self.status = status
        super().__init__(f"{status.value}: {message}")


class AuthenticityStatus(StrEnum):
    AUTHENTICATED = "AUTHENTICATED"
    UNAUTHENTICATED = "UNAUTHENTICATED"


class ConfidentialityStatus(StrEnum):
    PLAINTEXT = "PLAINTEXT"
    CONFIDENTIAL = "CONFIDENTIAL"


@dataclass(frozen=True, slots=True)
class ReplayBinding:
    """Authenticated replay identity passed to host-owned policy."""

    value: str
    signer_id: str
    signing_key_id: str
    payload_sha256: str


ReplayPolicyHook = Callable[[ReplayBinding], bool]


@dataclass(frozen=True, slots=True)
class TrustedSigner:
    """One out-of-band signer/key trust decision."""

    signer_id: str
    key_id: str
    public_key: bytes = field(repr=False)
    not_before_utc: datetime
    not_after_utc: datetime
    revoked: bool = False
    allowed_signature_suites: frozenset[str] = frozenset({SIGNATURE_SUITE})

    def __post_init__(self) -> None:
        _require_identifier("signer_id", self.signer_id)
        _require_key_id("signer key_id", self.key_id, prefix="ed25519")
        if len(self.public_key) != 32:
            raise ValueError("trusted Ed25519 public key must contain 32 bytes")
        Ed25519PublicKey.from_public_bytes(self.public_key)
        if not all(
            _is_utc(value) for value in (self.not_before_utc, self.not_after_utc)
        ):
            raise ValueError("signer validity timestamps must use UTC")
        if self.not_before_utc >= self.not_after_utc:
            raise ValueError("signer validity window must be increasing")
        if self.allowed_signature_suites != frozenset({SIGNATURE_SUITE}):
            raise ValueError("trusted signer suite policy is unsupported")


@dataclass(frozen=True, slots=True)
class ArchiveTrustPolicy:
    """Explicit host-owned signer trust, time, and replay decisions."""

    signers: tuple[TrustedSigner, ...]
    verification_time_utc: datetime
    prohibited_replay_bindings: frozenset[str] = frozenset()
    replay_policy_hook: ReplayPolicyHook | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not _is_utc(self.verification_time_utc):
            raise ValueError("verification_time_utc must use UTC")
        identities = [(item.signer_id, item.key_id) for item in self.signers]
        if len(identities) != len(set(identities)):
            raise ValueError("trust policy contains duplicate signer/key bindings")
        for value in self.prohibited_replay_bindings:
            if not _REPLAY_BINDING.fullmatch(value):
                raise ValueError("prohibited replay binding is malformed")


@dataclass(frozen=True, slots=True)
class ConfidentialityRequest:
    """One separately requested recipient encryption binding."""

    recipient_id: str
    recipient_public_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _require_identifier("recipient_id", self.recipient_id)
        if len(self.recipient_public_key) != 32:
            raise ValueError("X25519 recipient public key must contain 32 bytes")


@dataclass(frozen=True, slots=True)
class RecipientDecryptionKey:
    """Out-of-band recipient identity and raw private key."""

    recipient_id: str
    private_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _require_identifier("recipient_id", self.recipient_id)
        if len(self.private_key) != 32:
            raise ValueError("X25519 recipient private key must contain 32 bytes")


@dataclass(frozen=True, slots=True)
class ArchiveSecurityResult:
    """Security and preserved inner-archive identity for verification/import."""

    archive: str
    envelope_sha256: str
    payload_sha256: str
    project_id: str
    file_count: int
    completed_run_count: int
    authenticity_status: AuthenticityStatus
    confidentiality_status: ConfidentialityStatus
    signer_id: str | None
    signing_key_id: str | None
    replay_binding: str | None
    project_directory: str | None = None

    def as_dict(self) -> dict[str, int | str | None]:
        return {
            "archive": self.archive,
            "authenticity_status": self.authenticity_status.value,
            "completed_run_count": self.completed_run_count,
            "confidentiality_status": self.confidentiality_status.value,
            "envelope_sha256": self.envelope_sha256,
            "file_count": self.file_count,
            "payload_sha256": self.payload_sha256,
            "project_directory": self.project_directory,
            "project_id": self.project_id,
            "replay_binding": self.replay_binding,
            "signer_id": self.signer_id,
            "signing_key_id": self.signing_key_id,
        }


def read_exact_private_key(path: Path, *, label: str) -> bytes:
    """Read one externally owned raw private key without exposing its value."""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} must be an available regular file")
    contents = path.read_bytes()
    if len(contents) != 32:
        raise ValueError(f"{label} must contain exactly 32 bytes")
    return contents


def read_exact_public_key(path: Path, *, label: str) -> bytes:
    """Read one externally owned raw public key."""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} must be an available regular file")
    contents = path.read_bytes()
    if len(contents) != 32:
        raise ValueError(f"{label} must contain exactly 32 bytes")
    return contents


def load_archive_trust_policy(
    path: Path, *, verification_time_utc: datetime
) -> ArchiveTrustPolicy:
    """Load a strict host-owned public trust policy with no archive input."""
    if not path.is_file() or path.is_symlink():
        raise ValueError("archive trust policy must be an available regular file")
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("archive trust policy must be strict JSON") from error
    data = _exact_object(
        value,
        {"prohibited_replay_bindings", "schema_version", "signers"},
        "archive trust policy",
    )
    if data["schema_version"] != 1:
        raise ValueError("archive trust policy schema version is unsupported")
    signer_values = data["signers"]
    if not isinstance(signer_values, list):
        raise ValueError("archive trust policy signers must be a list")
    signers = tuple(_load_signer(item) for item in signer_values)
    prohibited = data["prohibited_replay_bindings"]
    if not isinstance(prohibited, list) or not all(
        isinstance(item, str) for item in prohibited
    ):
        raise ValueError("prohibited replay bindings must be a string list")
    if len(prohibited) != len(set(prohibited)):
        raise ValueError("prohibited replay bindings must be unique")
    return ArchiveTrustPolicy(
        signers=signers,
        verification_time_utc=verification_time_utc,
        prohibited_replay_bindings=frozenset(prohibited),
    )


def _load_signer(value: object) -> TrustedSigner:
    data = _exact_object(
        value,
        {
            "allowed_signature_suites",
            "key_id",
            "not_after_utc",
            "not_before_utc",
            "public_key",
            "revoked",
            "signer_id",
        },
        "trusted signer",
    )
    suites = data["allowed_signature_suites"]
    if not isinstance(suites, list) or not all(
        isinstance(item, str) for item in suites
    ):
        raise ValueError("allowed signature suites must be a string list")
    if len(suites) != len(set(suites)):
        raise ValueError("allowed signature suites must be unique")
    revoked = data["revoked"]
    if not isinstance(revoked, bool):
        raise ValueError("trusted signer revoked must be a Boolean")
    return TrustedSigner(
        signer_id=_string(data["signer_id"], "signer_id"),
        key_id=_string(data["key_id"], "key_id"),
        public_key=_decode_public_key(data["public_key"]),
        not_before_utc=_timestamp(data["not_before_utc"], "not_before_utc"),
        not_after_utc=_timestamp(data["not_after_utc"], "not_after_utc"),
        revoked=revoked,
        allowed_signature_suites=frozenset(suites),
    )


def _decode_public_key(value: object) -> bytes:
    encoded = _string(value, "public_key")
    if "=" in encoded:
        raise ValueError("trusted public key must use unpadded base64url")
    try:
        decoded = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error) as error:
        raise ValueError("trusted public key encoding is malformed") from error
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    if len(decoded) != 32 or canonical != encoded:
        raise ValueError("trusted public key encoding is malformed")
    return decoded


def _timestamp(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"{label} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError(f"{label} must be an RFC 3339 UTC timestamp") from error


def _exact_object(value: object, expected: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} fields are missing or unexpected")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_identifier(label: str, value: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a bounded ASCII identifier")


def _require_key_id(label: str, value: str, *, prefix: str) -> None:
    if not _KEY_ID.fullmatch(value) or not value.startswith(f"{prefix}:"):
        raise ValueError(f"{label} is malformed")


def _is_utc(value: datetime) -> bool:
    offset = value.utcoffset()
    return (
        value.tzinfo is not None
        and offset is not None
        and offset.total_seconds() == 0
    )
