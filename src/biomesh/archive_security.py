"""P5-WP03 authenticity and optional confidentiality for exact P4 archives."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import struct
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.hpke import AEAD, KDF, KEM, Suite

from biomesh.archive_security_types import (
    CONFIDENTIALITY_SUITE,
    SIGNATURE_SUITE,
    ArchiveSecurityError,
    ArchiveSecurityResult,
    ArchiveSecurityStatus,
    ArchiveTrustPolicy,
    AuthenticityStatus,
    ConfidentialityRequest,
    ConfidentialityStatus,
    RecipientDecryptionKey,
    ReplayBinding,
)
from biomesh.portable_project import (
    MAX_ARCHIVE_BYTES,
    _archive_security_status_bytes,
    _import_project_archive_with_status,
    _verify_archive_payload_bytes,
)
from biomesh.portable_project_types import PortableArchiveError

MAGIC = b"BIOMESH-SECURE-ARCHIVE-V1\r\n"
MAX_HEADER_BYTES = 65_536
_U64 = struct.Struct(">Q")
_SIGNING_DOMAIN = b"BioMesh secure archive signature input v1\0"
_REPLAY_DOMAIN = b"BioMesh secure archive replay binding v1\0"
_KEY_ID_DOMAINS = {
    "ed25519": b"BioMesh Ed25519 key id v1\0",
    "x25519": b"BioMesh X25519 key id v1\0",
}
_HPKE_INFO_DOMAIN = b"BioMesh secure archive HPKE info v1\0"
_HPKE_SUITE = Suite(KEM.X25519, KDF.HKDF_SHA256, AEAD.AES_256_GCM)
_HPKE_OVERHEAD_BYTES = 32 + 16
_PRIVATE_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
)
_IDENTIFIER_CHARACTERS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@/-"
)
_SECRET_PATH_SUFFIXES = frozenset({".key", ".p8", ".p12", ".pem", ".pk8"})
_SECRET_PATH_NAMES = frozenset(
    {
        "credentials",
        "id_ed25519",
        "id_rsa",
        "private-key",
        "private_key",
        "secret-key",
        "secret_key",
    }
)


@dataclass(frozen=True, slots=True)
class _OpenedEnvelope:
    payload: bytes
    envelope_sha256: str
    header: dict[str, Any]
    confidentiality_status: ConfidentialityStatus
    replay: ReplayBinding


def public_key_id(kind: str, public_key: bytes) -> str:
    """Derive the policy-defined key identifier from exact raw public bytes."""
    domain = _KEY_ID_DOMAINS.get(kind)
    if domain is None or len(public_key) != 32:
        raise ValueError("key ID input is unsupported")
    return f"{kind}:{hashlib.sha256(domain + public_key).hexdigest()}"


def create_secure_archive(
    payload_archive: Path,
    output: Path,
    *,
    signer_id: str,
    signing_private_key: bytes,
    confidentiality: ConfidentialityRequest | None = None,
) -> ArchiveSecurityResult:
    """Sign exact P4 bytes and optionally apply the separate AEAD envelope."""
    _require_new_output(output)
    payload = _read_bounded(payload_archive, limit=MAX_ARCHIVE_BYTES)
    manifest, _ = _verify_archive_payload_bytes(payload)
    _reject_secret_markers(payload)
    try:
        signing_key = Ed25519PrivateKey.from_private_bytes(signing_private_key)
    except (TypeError, ValueError) as error:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.SIGNER_KEY_MISMATCH,
            "signing private key is not an exact Ed25519 seed",
        ) from error
    public_bytes = signing_key.public_key().public_bytes_raw()
    signing_key_id = public_key_id("ed25519", public_bytes)
    header = _base_header(payload, signer_id, signing_key_id, confidentiality)
    signature_metadata = cast(dict[str, Any], header["signature"])
    replay = _replay_binding(header)
    signature_metadata["replay_binding"] = replay.value
    signature = signing_key.sign(_signed_data(header, payload))
    signature_metadata["value"] = _b64encode(signature)
    header_bytes = _canonical_json(header)
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.MALFORMED_ENVELOPE,
            "security header exceeds the declared limit",
        )

    if confidentiality is None:
        body = payload
        confidentiality_status = ConfidentialityStatus.PLAINTEXT
    else:
        body = _encrypt_payload(payload, header_bytes, confidentiality)
        confidentiality_status = ConfidentialityStatus.CONFIDENTIAL
    envelope = MAGIC + _U64.pack(len(header_bytes)) + header_bytes + body
    _atomic_write(output, envelope)
    return ArchiveSecurityResult(
        archive=str(output),
        envelope_sha256=_sha256(envelope),
        payload_sha256=_sha256(payload),
        project_id=manifest.project_id,
        file_count=len(manifest.files),
        completed_run_count=_completed_count(manifest.files),
        authenticity_status=AuthenticityStatus.AUTHENTICATED,
        confidentiality_status=confidentiality_status,
        signer_id=signer_id,
        signing_key_id=signing_key_id,
        replay_binding=replay.value,
    )


def verify_secure_archive(
    path: Path,
    policy: ArchiveTrustPolicy,
    *,
    decryption_key: RecipientDecryptionKey | None = None,
    require_confidentiality: bool = False,
) -> ArchiveSecurityResult:
    """Authenticate/decrypt before running every accepted P4 validation."""
    opened = _open_secure_archive(
        path,
        policy,
        decryption_key=decryption_key,
        require_confidentiality=require_confidentiality,
    )
    manifest, _ = _verify_archive_payload_bytes(opened.payload)
    signature = cast(dict[str, Any], opened.header["signature"])
    return ArchiveSecurityResult(
        archive=str(path),
        envelope_sha256=opened.envelope_sha256,
        payload_sha256=_sha256(opened.payload),
        project_id=manifest.project_id,
        file_count=len(manifest.files),
        completed_run_count=_completed_count(manifest.files),
        authenticity_status=AuthenticityStatus.AUTHENTICATED,
        confidentiality_status=opened.confidentiality_status,
        signer_id=cast(str, signature["signer_id"]),
        signing_key_id=cast(str, signature["key_id"]),
        replay_binding=opened.replay.value,
    )


def import_secure_archive(
    path: Path,
    project_directory: Path,
    policy: ArchiveTrustPolicy,
    *,
    decryption_key: RecipientDecryptionKey | None = None,
    require_confidentiality: bool = False,
) -> ArchiveSecurityResult:
    """Authenticate/decrypt/P4-verify, then atomically import with status."""
    if project_directory.exists() or project_directory.is_symlink():
        raise PortableArchiveError(
            f"project directory already exists: {project_directory}"
        )
    opened = _open_secure_archive(
        path,
        policy,
        decryption_key=decryption_key,
        require_confidentiality=require_confidentiality,
    )
    manifest, _ = _verify_archive_payload_bytes(opened.payload)
    signature = cast(dict[str, Any], opened.header["signature"])
    status_bytes = _archive_security_status_bytes(
        authenticity_status=AuthenticityStatus.AUTHENTICATED.value,
        confidentiality_status=opened.confidentiality_status.value,
        envelope_sha256=opened.envelope_sha256,
        payload_sha256=_sha256(opened.payload),
        signer_id=cast(str, signature["signer_id"]),
        signing_key_id=cast(str, signature["key_id"]),
        replay_binding=opened.replay.value,
    )
    descriptor, name = tempfile.mkstemp(
        prefix=f".{project_directory.name}.payload.", dir=project_directory.parent
    )
    temporary_archive = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(opened.payload)
            stream.flush()
            os.fsync(stream.fileno())
        imported = _import_project_archive_with_status(
            temporary_archive, project_directory, status_bytes
        )
    finally:
        temporary_archive.unlink(missing_ok=True)
    return ArchiveSecurityResult(
        archive=str(path),
        envelope_sha256=opened.envelope_sha256,
        payload_sha256=_sha256(opened.payload),
        project_id=manifest.project_id,
        file_count=imported.file_count,
        completed_run_count=imported.completed_run_count,
        authenticity_status=AuthenticityStatus.AUTHENTICATED,
        confidentiality_status=opened.confidentiality_status,
        signer_id=cast(str, signature["signer_id"]),
        signing_key_id=cast(str, signature["key_id"]),
        replay_binding=opened.replay.value,
        project_directory=str(project_directory),
    )


def _base_header(
    payload: bytes,
    signer_id: str,
    signing_key_id: str,
    confidentiality: ConfidentialityRequest | None,
) -> dict[str, Any]:
    _require_logical_id(signer_id, label="signer_id")
    signature: dict[str, Any] = {
        "key_id": signing_key_id,
        "public_key_encoding": "raw-rfc8032-base64url",
        "signature_encoding": "raw-rfc8032-base64url",
        "signer_id": signer_id,
        "suite": SIGNATURE_SUITE,
    }
    if confidentiality is None:
        confidentiality_metadata: dict[str, Any] = {"status": "PLAINTEXT"}
    else:
        recipient_key_id = public_key_id("x25519", confidentiality.recipient_public_key)
        confidentiality_metadata = {
            "ciphertext_encoding": "rfc9180-enc-concatenated-ciphertext",
            "key_encoding": "raw-rfc7748-base64url",
            "recipient_id": confidentiality.recipient_id,
            "recipient_key_id": recipient_key_id,
            "status": "CONFIDENTIAL",
            "suite": CONFIDENTIALITY_SUITE,
        }
    return {
        "archive_security_format": "biomesh-secure-archive",
        "confidentiality": confidentiality_metadata,
        "payload": {
            "encoding": "raw-biomesh-portable-project",
            "sha256": _sha256(payload),
            "size_bytes": len(payload),
        },
        "schema_version": 1,
        "signature": signature,
    }


def _encrypt_payload(
    payload: bytes,
    header_bytes: bytes,
    request: ConfidentialityRequest,
) -> bytes:
    try:
        return _HPKE_SUITE.encrypt(
            payload,
            X25519PublicKey.from_public_bytes(request.recipient_public_key),
            info=_hpke_info(header_bytes),
        )
    except (TypeError, ValueError) as error:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.RECIPIENT_MISMATCH,
            "recipient public key is invalid",
        ) from error


def _open_secure_archive(
    path: Path,
    policy: ArchiveTrustPolicy,
    *,
    decryption_key: RecipientDecryptionKey | None,
    require_confidentiality: bool,
) -> _OpenedEnvelope:
    envelope = _read_bounded(
        path, limit=len(MAGIC) + 8 + MAX_HEADER_BYTES + MAX_ARCHIVE_BYTES + 16
    )
    header, header_bytes, body = _parse_envelope(envelope)
    confidentiality = cast(dict[str, Any], header["confidentiality"])
    payload_metadata = cast(dict[str, Any], header["payload"])
    declared_size = cast(int, payload_metadata["size_bytes"])
    status = cast(str, confidentiality["status"])
    if status == "PLAINTEXT":
        if len(body) != declared_size:
            raise ArchiveSecurityError(
                ArchiveSecurityStatus.MALFORMED_ENVELOPE,
                "plaintext body size does not match signed metadata",
            )
        if require_confidentiality:
            raise ArchiveSecurityError(
                ArchiveSecurityStatus.CONFIDENTIALITY_REQUIRED,
                "host policy requires a confidential archive",
            )
        payload = body
        confidentiality_status = ConfidentialityStatus.PLAINTEXT
    elif status == "CONFIDENTIAL":
        if len(body) != declared_size + _HPKE_OVERHEAD_BYTES:
            raise ArchiveSecurityError(
                ArchiveSecurityStatus.DECRYPTION_FAILED,
                "confidential body size does not match authenticated metadata",
            )
        if decryption_key is None:
            raise ArchiveSecurityError(
                ArchiveSecurityStatus.DECRYPTION_KEY_REQUIRED,
                "confidential archive requires an explicit recipient key",
            )
        payload = _decrypt_payload(body, header, header_bytes, decryption_key)
        confidentiality_status = ConfidentialityStatus.CONFIDENTIAL
    else:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.MALFORMED_ENVELOPE,
            "confidentiality status is invalid",
        )
    _verify_payload_identity(header, payload)
    replay = _verify_signature_and_policy(header, payload, policy)
    if replay.value in policy.prohibited_replay_bindings:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.REPLAY_REJECTED,
            "host policy prohibits this authenticated replay binding",
        )
    if policy.replay_policy_hook is not None and not policy.replay_policy_hook(replay):
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.REPLAY_REJECTED,
            "host replay policy rejected this authenticated archive",
        )
    return _OpenedEnvelope(
        payload=payload,
        envelope_sha256=_sha256(envelope),
        header=header,
        confidentiality_status=confidentiality_status,
        replay=replay,
    )


def _parse_envelope(
    envelope: bytes,
) -> tuple[dict[str, Any], bytes, bytes]:
    if not envelope.startswith(MAGIC) or len(envelope) < len(MAGIC) + 8:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.LEGACY_POLICY_REQUIRED,
            "input is not a schema-version 1 secure archive",
        )
    header_size = _U64.unpack_from(envelope, len(MAGIC))[0]
    if not 1 <= header_size <= MAX_HEADER_BYTES:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.MALFORMED_ENVELOPE,
            "security header size is outside the declared bound",
        )
    header_start = len(MAGIC) + 8
    header_end = header_start + header_size
    if header_end > len(envelope):
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.MALFORMED_ENVELOPE,
            "security header is truncated",
        )
    header_bytes = envelope[header_start:header_end]
    header = _strict_header(header_bytes)
    return header, header_bytes, envelope[header_end:]


def _strict_header(contents: bytes) -> dict[str, Any]:
    try:
        value = json.loads(contents, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.MALFORMED_ENVELOPE,
            "security header is not strict JSON",
        ) from error
    if not isinstance(value, dict) or _canonical_json(value) != contents:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.MALFORMED_ENVELOPE,
            "security header is not canonical JSON",
        )
    header = cast(dict[str, Any], value)
    _validate_header_fields(header)
    return header


def _validate_header_fields(header: dict[str, Any]) -> None:
    _exact_fields(
        header,
        {
            "archive_security_format",
            "confidentiality",
            "payload",
            "schema_version",
            "signature",
        },
        "security header",
    )
    if header["archive_security_format"] != "biomesh-secure-archive":
        raise _malformed("archive security format is invalid")
    if header["schema_version"] != 1:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.UNSUPPORTED_VERSION,
            "archive security schema version is unsupported",
        )
    payload = _object(header["payload"], "payload")
    _exact_fields(payload, {"encoding", "sha256", "size_bytes"}, "payload")
    if payload["encoding"] != "raw-biomesh-portable-project":
        raise _malformed("payload encoding is unsupported")
    _sha256_value(payload["sha256"], "payload SHA-256")
    size = payload["size_bytes"]
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or not 0 < size <= MAX_ARCHIVE_BYTES
    ):
        raise _malformed("payload size is outside the declared bound")
    signature = _object(header["signature"], "signature")
    _exact_fields(
        signature,
        {
            "key_id",
            "public_key_encoding",
            "replay_binding",
            "signature_encoding",
            "signer_id",
            "suite",
            "value",
        },
        "signature",
    )
    if signature["suite"] != SIGNATURE_SUITE:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.UNSUPPORTED_ALGORITHM,
            "signature suite is unsupported",
        )
    if (
        signature["public_key_encoding"] != "raw-rfc8032-base64url"
        or signature["signature_encoding"] != "raw-rfc8032-base64url"
    ):
        raise _malformed("signature encoding is unsupported")
    _require_logical_id(signature["signer_id"], label="signer_id")
    _key_id(signature["key_id"], prefix="ed25519")
    _sha256_value(signature["replay_binding"], "replay binding")
    _b64decode(signature["value"], expected=64, label="signature")
    confidentiality = _object(header["confidentiality"], "confidentiality")
    if confidentiality.get("status") == "PLAINTEXT":
        _exact_fields(confidentiality, {"status"}, "plaintext confidentiality")
    elif confidentiality.get("status") == "CONFIDENTIAL":
        _exact_fields(
            confidentiality,
            {
                "ciphertext_encoding",
                "key_encoding",
                "recipient_id",
                "recipient_key_id",
                "status",
                "suite",
            },
            "confidentiality",
        )
        if confidentiality["suite"] != CONFIDENTIALITY_SUITE:
            raise ArchiveSecurityError(
                ArchiveSecurityStatus.UNSUPPORTED_ALGORITHM,
                "confidentiality suite is unsupported",
            )
        if (
            confidentiality["ciphertext_encoding"]
            != "rfc9180-enc-concatenated-ciphertext"
            or confidentiality["key_encoding"] != "raw-rfc7748-base64url"
        ):
            raise _malformed("confidentiality encoding is unsupported")
        _require_logical_id(confidentiality["recipient_id"], label="recipient_id")
        _key_id(confidentiality["recipient_key_id"], prefix="x25519")
    else:
        raise _malformed("confidentiality status is invalid")


def _decrypt_payload(
    body: bytes,
    header: dict[str, Any],
    header_bytes: bytes,
    recipient: RecipientDecryptionKey,
) -> bytes:
    confidentiality = cast(dict[str, Any], header["confidentiality"])
    if confidentiality["recipient_id"] != recipient.recipient_id:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.RECIPIENT_MISMATCH,
            "recipient identity does not match the confidential envelope",
        )
    try:
        private_key = X25519PrivateKey.from_private_bytes(recipient.private_key)
        public_bytes = private_key.public_key().public_bytes_raw()
        if public_key_id("x25519", public_bytes) != confidentiality["recipient_key_id"]:
            raise ArchiveSecurityError(
                ArchiveSecurityStatus.RECIPIENT_MISMATCH,
                "recipient key does not match the confidential envelope",
            )
        return _HPKE_SUITE.decrypt(
            body,
            private_key,
            info=_hpke_info(header_bytes),
        )
    except ArchiveSecurityError:
        raise
    except (InvalidTag, TypeError, ValueError) as error:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.DECRYPTION_FAILED,
            "authenticated decryption failed",
        ) from error
def _verify_signature_and_policy(
    header: dict[str, Any], payload: bytes, policy: ArchiveTrustPolicy
) -> ReplayBinding:
    signature = cast(dict[str, Any], header["signature"])
    matches = [
        item for item in policy.signers if item.signer_id == signature["signer_id"]
    ]
    if not matches:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.UNKNOWN_SIGNER,
            "signer is absent from host trust policy",
        )
    keyed = [item for item in matches if item.key_id == signature["key_id"]]
    if len(keyed) != 1:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.SIGNER_KEY_MISMATCH,
            "signer key binding does not match host trust policy",
        )
    trusted = keyed[0]
    if public_key_id("ed25519", trusted.public_key) != trusted.key_id:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.SIGNER_KEY_MISMATCH,
            "host trust policy key ID does not match its public key",
        )
    if signature["suite"] not in trusted.allowed_signature_suites:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.UNSUPPORTED_ALGORITHM,
            "host policy prohibits the declared signature suite",
        )
    if trusted.revoked:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.REVOKED_SIGNER,
            "host trust policy marks the signer key revoked",
        )
    now = policy.verification_time_utc
    if now < trusted.not_before_utc:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.SIGNER_NOT_YET_VALID,
            "signer key is not yet valid at the host verification time",
        )
    if now >= trusted.not_after_utc:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.EXPIRED_SIGNER,
            "signer key is expired at the host verification time",
        )
    expected_replay = _replay_binding(header)
    if signature["replay_binding"] != expected_replay.value:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.INVALID_SIGNATURE,
            "replay binding does not match signed metadata",
        )
    try:
        Ed25519PublicKey.from_public_bytes(trusted.public_key).verify(
            _b64decode(signature["value"], expected=64, label="signature"),
            _signed_data(header, payload),
        )
    except (InvalidSignature, TypeError, ValueError) as error:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.INVALID_SIGNATURE,
            "signature does not authenticate the exact payload and metadata",
        ) from error
    return expected_replay


def _verify_payload_identity(header: dict[str, Any], payload: bytes) -> None:
    metadata = cast(dict[str, Any], header["payload"])
    if len(payload) != metadata["size_bytes"] or _sha256(payload) != metadata["sha256"]:
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.INVALID_SIGNATURE,
            "payload identity does not match signed metadata",
        )


def _signed_data(header: dict[str, Any], payload: bytes) -> bytes:
    signed_header = _without_signature_value(header)
    metadata = _canonical_json(signed_header)
    return (
        _SIGNING_DOMAIN
        + _U64.pack(len(metadata))
        + metadata
        + _U64.pack(len(payload))
        + payload
    )


def _replay_binding(header: dict[str, Any]) -> ReplayBinding:
    signature = cast(dict[str, Any], header["signature"])
    payload = cast(dict[str, Any], header["payload"])
    confidentiality = cast(dict[str, Any], header["confidentiality"])
    fields = {
        "confidentiality": confidentiality,
        "payload_sha256": payload["sha256"],
        "payload_size_bytes": payload["size_bytes"],
        "schema_version": header["schema_version"],
        "signature_suite": signature["suite"],
        "signer_id": signature["signer_id"],
        "signing_key_id": signature["key_id"],
    }
    value = _sha256(_REPLAY_DOMAIN + _canonical_json(fields))
    return ReplayBinding(
        value, signature["signer_id"], signature["key_id"], payload["sha256"]
    )


def _without_signature_value(header: dict[str, Any]) -> dict[str, Any]:
    clone = cast(dict[str, Any], json.loads(_canonical_json(header)))
    signature = cast(dict[str, Any], clone["signature"])
    signature.pop("value", None)
    return clone


def _hpke_info(header_bytes: bytes) -> bytes:
    return _HPKE_INFO_DOMAIN + _U64.pack(len(header_bytes)) + header_bytes


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: object, *, expected: int, label: str) -> bytes:
    if not isinstance(value, str) or not value or "=" in value:
        raise _malformed(f"{label} encoding is malformed")
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error) as error:
        raise _malformed(f"{label} encoding is malformed") from error
    if len(decoded) != expected or _b64encode(decoded) != value:
        raise _malformed(f"{label} encoding or length is malformed")
    return decoded


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _malformed(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _exact_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise _malformed(f"{label} fields are missing, duplicated, or unexpected")


def _require_logical_id(value: object, *, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or not value.isascii()
        or not value[0].isalnum()
        or any(character not in _IDENTIFIER_CHARACTERS for character in value)
    ):
        raise _malformed(f"{label} is malformed")


def _key_id(value: object, *, prefix: str) -> None:
    if (
        not isinstance(value, str)
        or not value.startswith(prefix + ":")
        or len(value) != len(prefix) + 65
    ):
        raise _malformed(f"{prefix} key ID is malformed")
    _sha256_value(value.split(":", 1)[1], f"{prefix} key ID")


def _sha256_value(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _malformed(f"{label} is malformed")


def _malformed(message: str) -> ArchiveSecurityError:
    return ArchiveSecurityError(ArchiveSecurityStatus.MALFORMED_ENVELOPE, message)


def _read_bounded(path: Path, *, limit: int) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise _malformed("archive input must be an available regular file")
    size = path.stat().st_size
    if size < 1 or size > limit:
        raise _malformed("archive input exceeds the declared size bound")
    return path.read_bytes()


def _require_new_output(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise PortableArchiveError(f"secure archive already exists: {path}")
    if not path.parent.is_dir():
        raise PortableArchiveError("secure archive parent directory does not exist")


def _atomic_write(path: Path, contents: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _reject_secret_markers(payload: bytes) -> None:
    if any(marker in payload for marker in _PRIVATE_MARKERS):
        raise ArchiveSecurityError(
            ArchiveSecurityStatus.SECRET_MATERIAL_REJECTED,
            "portable payload contains a prohibited private-key marker",
        )
    try:
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
            for name in archive.namelist():
                path = Path(name)
                lowered_stem = path.stem.lower()
                if (
                    path.suffix.lower() in _SECRET_PATH_SUFFIXES
                    or lowered_stem in _SECRET_PATH_NAMES
                ):
                    raise ArchiveSecurityError(
                        ArchiveSecurityStatus.SECRET_MATERIAL_REJECTED,
                        "portable payload contains a prohibited secret-bearing path",
                    )
    except zipfile.BadZipFile:
        # Complete P4 verification has already rejected this input.
        return


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _completed_count(records: Sequence[object]) -> int:
    return sum(
        getattr(record, "path", "").endswith("/.biomesh-completion.json")
        for record in records
    )
