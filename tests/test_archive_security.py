"""Focused P5-WP03 tests for MT-AR-01 through MT-AR-14."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from biomesh.__main__ import main
from biomesh.archive_security import (
    MAGIC,
    _base_header,
    _canonical_json,
    _replay_binding,
    _signed_data,
    create_secure_archive,
    import_secure_archive,
    public_key_id,
    verify_secure_archive,
)
from biomesh.archive_security_types import (
    SIGNATURE_SUITE,
    ArchiveSecurityError,
    ArchiveSecurityStatus,
    ArchiveTrustPolicy,
    ConfidentialityRequest,
    RecipientDecryptionKey,
    TrustedSigner,
)
from biomesh.portable_project import (
    ARCHIVE_SECURITY_STATUS,
    export_project_archive,
    import_project_archive,
)
from biomesh.portable_project_types import PortableArchiveError
from biomesh.project_campaign import (
    CampaignRecord,
    CampaignService,
    ExperimentRecord,
    ProjectDefinition,
    ProjectRecord,
    RunExecutionRequest,
    SeedPolicy,
    SweepPoint,
    accepted_core_execution_identity,
    create_project,
)

# Test keys are generated in memory for this process and are never tracked fixtures.
_SIGNING_SEED = Ed25519PrivateKey.generate().private_bytes_raw()
_RECIPIENT_SEED = X25519PrivateKey.generate().private_bytes_raw()
_OTHER_RECIPIENT_SEED = X25519PrivateKey.generate().private_bytes_raw()
_NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)


def _project(tmp_path: Path, *, compact: bytes = b'{"result":"safe"}\n') -> Path:
    fixture = Path("experiments/producer.yaml")
    definition = ProjectDefinition(
        schema_version=2,
        project=ProjectRecord(
            schema_version=1,
            project_id="secure-portable-project",
            title="Secure archive software validation",
            description="Manufactured validation only.",
        ),
        experiments=[
            ExperimentRecord(
                schema_version=1,
                experiment_id="accepted-producer",
                title="Accepted producer fixture",
                fixture_file=str(fixture.resolve()),
                fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                calibration_status="CALIBRATION_REQUIRED",
                notes="Accepted zero-plugin path.",
            )
        ],
        campaigns=[
            CampaignRecord(
                schema_version=1,
                campaign_id="completed",
                experiment_id="accepted-producer",
                title="Completed compact result",
                replicate_count=1,
                seed_policy=SeedPolicy(kind="explicit", seeds=[101]),
                sweep_matrix=[
                    SweepPoint(point_id="producer-point", condition_id="producer")
                ],
            )
        ],
        execution_identity=accepted_core_execution_identity(Path.cwd()),
    )
    definition_file = tmp_path / "definition.json"
    definition_file.write_text(
        definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    project = create_project(definition_file, tmp_path / "project")

    def executor(_request: RunExecutionRequest, output: Path) -> None:
        (output / "compact.json").write_bytes(compact)

    assert (
        CampaignService(project, executor=executor).resume("completed").completed == 1
    )
    return project


def _unsigned_archive(
    tmp_path: Path, *, compact: bytes = b'{"result":"safe"}\n'
) -> Path:
    archive = tmp_path / "payload.biomesh"
    export_project_archive(_project(tmp_path, compact=compact), archive)
    return archive


def _signing_public_key() -> bytes:
    return (
        Ed25519PrivateKey.from_private_bytes(_SIGNING_SEED)
        .public_key()
        .public_bytes_raw()
    )


def _recipient_private(seed: bytes = _RECIPIENT_SEED) -> X25519PrivateKey:
    return X25519PrivateKey.from_private_bytes(seed)


def _trust_policy(
    *,
    signer_id: str = "lab.example/alice",
    revoked: bool = False,
    not_before: datetime | None = None,
    not_after: datetime | None = None,
    public_key: bytes | None = None,
    prohibited: frozenset[str] = frozenset(),
) -> ArchiveTrustPolicy:
    key = _signing_public_key() if public_key is None else public_key
    return ArchiveTrustPolicy(
        signers=(
            TrustedSigner(
                signer_id=signer_id,
                key_id=public_key_id("ed25519", key),
                public_key=key,
                not_before_utc=not_before or _NOW - timedelta(days=1),
                not_after_utc=not_after or _NOW + timedelta(days=1),
                revoked=revoked,
            ),
        ),
        verification_time_utc=_NOW,
        prohibited_replay_bindings=prohibited,
    )


def _secure(
    tmp_path: Path,
    *,
    confidential: bool = False,
    compact: bytes = b'{"result":"safe"}\n',
) -> tuple[Path, Path]:
    payload = _unsigned_archive(tmp_path, compact=compact)
    output = tmp_path / "secure.biomesh"
    request = None
    if confidential:
        request = ConfidentialityRequest(
            recipient_id="lab.example/bob",
            recipient_public_key=_recipient_private().public_key().public_bytes_raw(),
        )
    create_secure_archive(
        payload,
        output,
        signer_id="lab.example/alice",
        signing_private_key=_SIGNING_SEED,
        confidentiality=request,
    )
    return payload, output


def _decryption_key(seed: bytes = _RECIPIENT_SEED) -> RecipientDecryptionKey:
    return RecipientDecryptionKey(recipient_id="lab.example/bob", private_key=seed)


def _envelope_parts(path: Path) -> tuple[dict[str, Any], bytes]:
    contents = path.read_bytes()
    size = struct.unpack_from(">Q", contents, len(MAGIC))[0]
    start = len(MAGIC) + 8
    return json.loads(contents[start : start + size]), contents[start + size :]


def _write_envelope(path: Path, header: dict[str, Any], body: bytes) -> None:
    header_bytes = _canonical_json(header)
    path.write_bytes(MAGIC + struct.pack(">Q", len(header_bytes)) + header_bytes + body)


def _signed_arbitrary_payload(path: Path, payload: bytes) -> None:
    private = Ed25519PrivateKey.from_private_bytes(_SIGNING_SEED)
    key_id = public_key_id("ed25519", private.public_key().public_bytes_raw())
    header = _base_header(payload, "lab.example/alice", key_id, None)
    signature = cast(dict[str, Any], header["signature"])
    signature["replay_binding"] = _replay_binding(header).value
    signature["value"] = (
        base64.urlsafe_b64encode(private.sign(_signed_data(header, payload)))
        .rstrip(b"=")
        .decode("ascii")
    )
    _write_envelope(path, header, payload)


def test_signed_plaintext_authenticates_before_atomic_import_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    """MT-AR-01/05/07/08: exact payload and completed bytes remain separate."""
    payload, secure = _secure(tmp_path)
    first_secure_bytes = secure.read_bytes()
    result = verify_secure_archive(secure, _trust_policy())
    assert result.payload_sha256 == hashlib.sha256(payload.read_bytes()).hexdigest()
    assert result.authenticity_status == "AUTHENTICATED"
    assert result.confidentiality_status == "PLAINTEXT"

    imported = tmp_path / "imported"
    imported_result = import_secure_archive(secure, imported, _trust_policy())
    assert imported_result.project_directory == str(imported)
    status = json.loads((imported / ARCHIVE_SECURITY_STATUS).read_bytes())
    assert status["authenticity_status"] == "AUTHENTICATED"
    assert status["confidentiality_status"] == "PLAINTEXT"
    source_completed = next((tmp_path / "project" / "artifacts").iterdir())
    imported_completed = imported / "artifacts" / source_completed.name
    assert {
        item.relative_to(source_completed): item.read_bytes()
        for item in source_completed.rglob("*")
        if item.is_file()
    } == {
        item.relative_to(imported_completed): item.read_bytes()
        for item in imported_completed.rglob("*")
        if item.is_file()
    }

    second = tmp_path / "secure-again.biomesh"
    create_secure_archive(
        payload,
        second,
        signer_id="lab.example/alice",
        signing_private_key=_SIGNING_SEED,
    )
    assert second.read_bytes() == first_secure_bytes
    assert payload.read_bytes().startswith(b"PK")


def test_changed_or_repacked_payload_fails_before_import_without_side_effect(
    tmp_path: Path,
) -> None:
    """MT-AR-01/02: P4 checksum consistency never substitutes for signature."""
    _payload, secure = _secure(tmp_path)
    header, body = _envelope_parts(secure)
    body = body[:-1] + bytes([body[-1] ^ 1])
    changed = tmp_path / "changed.biomesh"
    _write_envelope(changed, header, body)
    target = tmp_path / "target"
    with pytest.raises(ArchiveSecurityError) as caught:
        import_secure_archive(changed, target, _trust_policy())
    assert caught.value.status is ArchiveSecurityStatus.INVALID_SIGNATURE
    assert not target.exists()

    repacked = tmp_path / "repacked-inner.biomesh"
    with (
        zipfile.ZipFile(tmp_path / "payload.biomesh") as source,
        zipfile.ZipFile(
            repacked, mode="w", compression=zipfile.ZIP_STORED
        ) as target_archive,
    ):
        for name in reversed(source.namelist()):
            target_archive.writestr(name, source.read(name))
    substituted = tmp_path / "substituted.biomesh"
    _write_envelope(substituted, header, repacked.read_bytes())
    with pytest.raises(ArchiveSecurityError):
        verify_secure_archive(substituted, _trust_policy())


def test_archive_self_assertion_unknown_and_key_mismatch_are_not_trust(
    tmp_path: Path,
) -> None:
    """MT-AR-03/04: trust is host-owned and signer/key matching is exact."""
    _payload, secure = _secure(tmp_path)
    empty = ArchiveTrustPolicy(signers=(), verification_time_utc=_NOW)
    with pytest.raises(ArchiveSecurityError) as unknown:
        verify_secure_archive(secure, empty)
    assert unknown.value.status is ArchiveSecurityStatus.UNKNOWN_SIGNER

    other_key = Ed25519PrivateKey.generate()
    with pytest.raises(ArchiveSecurityError) as mismatch:
        verify_secure_archive(
            secure,
            _trust_policy(public_key=other_key.public_key().public_bytes_raw()),
        )
    assert mismatch.value.status is ArchiveSecurityStatus.SIGNER_KEY_MISMATCH


@pytest.mark.parametrize(
    ("policy", "status"),
    [
        (_trust_policy(revoked=True), ArchiveSecurityStatus.REVOKED_SIGNER),
        (
            _trust_policy(
                not_before=_NOW + timedelta(seconds=1),
                not_after=_NOW + timedelta(days=1),
            ),
            ArchiveSecurityStatus.SIGNER_NOT_YET_VALID,
        ),
        (
            _trust_policy(
                not_before=_NOW - timedelta(days=1),
                not_after=_NOW,
            ),
            ArchiveSecurityStatus.EXPIRED_SIGNER,
        ),
    ],
)
def test_revoked_or_invalid_time_signer_has_distinct_actionable_status(
    tmp_path: Path, policy: ArchiveTrustPolicy, status: ArchiveSecurityStatus
) -> None:
    """MT-AR-04: revoked, not-yet-valid, and expired states fail distinctly."""
    _payload, secure = _secure(tmp_path)
    with pytest.raises(ArchiveSecurityError) as caught:
        verify_secure_archive(secure, policy)
    assert caught.value.status is status


def test_unsupported_malformed_or_metadata_substitution_never_falls_back(
    tmp_path: Path,
) -> None:
    """MT-AR-04/05/11: no suite guessing, downgrade, or malformed fallback."""
    _payload, secure = _secure(tmp_path)
    header, body = _envelope_parts(secure)
    cast(dict[str, Any], header["signature"])["suite"] = "BMAS-SIG-0-GUESS"
    unsupported = tmp_path / "unsupported.biomesh"
    _write_envelope(unsupported, header, body)
    with pytest.raises(ArchiveSecurityError) as caught:
        verify_secure_archive(unsupported, _trust_policy())
    assert caught.value.status is ArchiveSecurityStatus.UNSUPPORTED_ALGORITHM

    malformed = tmp_path / "malformed.biomesh"
    duplicate = b'{"schema_version":1,"schema_version":1}\n'
    malformed.write_bytes(MAGIC + struct.pack(">Q", len(duplicate)) + duplicate + body)
    with pytest.raises(ArchiveSecurityError) as duplicate_error:
        verify_secure_archive(malformed, _trust_policy())
    assert duplicate_error.value.status is ArchiveSecurityStatus.MALFORMED_ENVELOPE

    version_header, version_body = _envelope_parts(secure)
    version_header["schema_version"] = 2
    future = tmp_path / "future.biomesh"
    _write_envelope(future, version_header, version_body)
    with pytest.raises(ArchiveSecurityError) as version_error:
        verify_secure_archive(future, _trust_policy())
    assert version_error.value.status is ArchiveSecurityStatus.UNSUPPORTED_VERSION


def test_legacy_unsigned_policy_is_explicit_and_status_is_durable(
    tmp_path: Path,
) -> None:
    """MT-AR-06/07: legacy import requires opt-in and cannot gain trust."""
    payload = _unsigned_archive(tmp_path)
    rejected = tmp_path / "rejected"
    with pytest.raises(PortableArchiveError, match="explicit allow_unauthenticated"):
        import_project_archive(payload, rejected)
    assert not rejected.exists()
    imported = tmp_path / "legacy"
    result = import_project_archive(payload, imported, allow_unauthenticated=True)
    assert result.authenticity_status == "UNAUTHENTICATED"
    status = json.loads((imported / ARCHIVE_SECURITY_STATUS).read_bytes())
    assert status["authenticity_status"] == "UNAUTHENTICATED"
    assert status["signer_id"] is None


def test_confidential_archive_requires_exact_recipient_and_authenticates_body(
    tmp_path: Path,
) -> None:
    """MT-AR-09/10: wrong key and altered ciphertext fail before publication."""
    _payload, secure = _secure(tmp_path, confidential=True)
    target = tmp_path / "wrong-target"
    with pytest.raises(ArchiveSecurityError) as wrong:
        import_secure_archive(
            secure,
            target,
            _trust_policy(),
            decryption_key=_decryption_key(_OTHER_RECIPIENT_SEED),
        )
    assert wrong.value.status is ArchiveSecurityStatus.RECIPIENT_MISMATCH
    assert not target.exists()

    accepted = verify_secure_archive(
        secure,
        _trust_policy(),
        decryption_key=_decryption_key(),
        require_confidentiality=True,
    )
    assert accepted.authenticity_status == "AUTHENTICATED"
    assert accepted.confidentiality_status == "CONFIDENTIAL"
    imported = tmp_path / "confidential-import"
    import_secure_archive(
        secure,
        imported,
        _trust_policy(),
        decryption_key=_decryption_key(),
        require_confidentiality=True,
    )
    status = json.loads((imported / ARCHIVE_SECURITY_STATUS).read_bytes())
    assert status["authenticity_status"] == "AUTHENTICATED"
    assert status["confidentiality_status"] == "CONFIDENTIAL"

    header, body = _envelope_parts(secure)
    for label, changed_body in {
        "modified": body[:-1] + bytes([body[-1] ^ 1]),
        "truncated": body[:-1],
        "extended": body + b"x",
        "reordered": body[1:] + body[:1],
    }.items():
        altered = tmp_path / f"{label}.biomesh"
        _write_envelope(altered, header, changed_body)
        with pytest.raises(ArchiveSecurityError) as caught:
            verify_secure_archive(
                altered,
                _trust_policy(),
                decryption_key=_decryption_key(),
            )
        assert caught.value.status is ArchiveSecurityStatus.DECRYPTION_FAILED


def test_authenticated_metadata_tamper_and_property_confusion_fail_closed(
    tmp_path: Path,
) -> None:
    """MT-AR-10/11/12: metadata and requested properties are independent."""
    _payload, confidential = _secure(tmp_path, confidential=True)
    header, body = _envelope_parts(confidential)
    signature = cast(dict[str, Any], header["signature"])
    value = cast(str, signature["value"])
    signature["value"] = ("B" if value[0] == "A" else "A") + value[1:]
    changed = tmp_path / "metadata-tamper.biomesh"
    _write_envelope(changed, header, body)
    with pytest.raises(ArchiveSecurityError) as caught:
        verify_secure_archive(
            changed, _trust_policy(), decryption_key=_decryption_key()
        )
    assert caught.value.status is ArchiveSecurityStatus.DECRYPTION_FAILED

    suite_header, suite_body = _envelope_parts(confidential)
    confidentiality = cast(dict[str, Any], suite_header["confidentiality"])
    confidentiality["suite"] = "BMAS-ENC-0-GUESS"
    unsupported = tmp_path / "unsupported-confidentiality.biomesh"
    _write_envelope(unsupported, suite_header, suite_body)
    with pytest.raises(ArchiveSecurityError) as suite_error:
        verify_secure_archive(
            unsupported, _trust_policy(), decryption_key=_decryption_key()
        )
    assert suite_error.value.status is ArchiveSecurityStatus.UNSUPPORTED_ALGORITHM

    plain_root = tmp_path / "plain-root"
    plain_root.mkdir()
    _plain_payload, plain = _secure(plain_root)
    with pytest.raises(ArchiveSecurityError) as required:
        verify_secure_archive(plain, _trust_policy(), require_confidentiality=True)
    assert required.value.status is ArchiveSecurityStatus.CONFIDENTIALITY_REQUIRED


def test_replay_hook_runs_after_authentication_and_before_import(
    tmp_path: Path,
) -> None:
    """MT-AR-04: host replay policy rejects with no project publication."""
    _payload, secure = _secure(tmp_path)
    verified = verify_secure_archive(secure, _trust_policy())
    assert verified.replay_binding is not None
    policy = _trust_policy(prohibited=frozenset({verified.replay_binding}))
    target = tmp_path / "replay-target"
    with pytest.raises(ArchiveSecurityError) as caught:
        import_secure_archive(secure, target, policy)
    assert caught.value.status is ArchiveSecurityStatus.REPLAY_REJECTED
    assert not target.exists()


def test_private_key_marker_and_malformed_inner_p4_are_rejected(tmp_path: Path) -> None:
    """MT-AR-13/14: secret-like content and invalid inner P4 never publish."""
    secret_archive = _unsigned_archive(
        tmp_path,
        compact=b"-----BEGIN PRIVATE KEY-----\nnot-a-key\n",
    )
    output = tmp_path / "must-not-exist.biomesh"
    with pytest.raises(ArchiveSecurityError) as secret:
        create_secure_archive(
            secret_archive,
            output,
            signer_id="lab.example/alice",
            signing_private_key=_SIGNING_SEED,
        )
    assert secret.value.status is ArchiveSecurityStatus.SECRET_MATERIAL_REJECTED
    assert "not-a-key" not in str(secret.value)
    assert not output.exists()

    malformed = tmp_path / "signed-malformed.biomesh"
    _signed_arbitrary_payload(malformed, b"not a P4 ZIP")
    target = tmp_path / "malformed-target"
    with pytest.raises(PortableArchiveError, match="invalid portable archive payload"):
        import_secure_archive(malformed, target, _trust_policy())
    assert not target.exists()


def test_secure_archive_cli_uses_external_keys_and_host_policy(tmp_path: Path) -> None:
    """Production CLI signs, verifies, and imports without retaining key bytes."""
    payload = _unsigned_archive(tmp_path)
    private_path = tmp_path / "signing.key"
    private_path.write_bytes(_SIGNING_SEED)
    secure = tmp_path / "cli-secure.biomesh"
    assert (
        main(
            [
                "project",
                "secure-archive",
                str(payload),
                "--output",
                str(secure),
                "--signer-id",
                "lab.example/alice",
                "--signing-private-key",
                str(private_path),
            ]
        )
        == 0
    )
    public = _signing_public_key()
    encoded = base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii")
    policy_path = tmp_path / "trust.json"
    policy_path.write_text(
        json.dumps(
            {
                "prohibited_replay_bindings": [],
                "schema_version": 1,
                "signers": [
                    {
                        "allowed_signature_suites": [SIGNATURE_SUITE],
                        "key_id": public_key_id("ed25519", public),
                        "not_after_utc": "2099-01-01T00:00:00Z",
                        "not_before_utc": "2020-01-01T00:00:00Z",
                        "public_key": encoded,
                        "revoked": False,
                        "signer_id": "lab.example/alice",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "project",
                "verify-secure-archive",
                str(secure),
                "--trust-policy",
                str(policy_path),
            ]
        )
        == 0
    )
    imported = tmp_path / "cli-imported"
    assert (
        main(
            [
                "project",
                "import-secure-archive",
                str(secure),
                str(imported),
                "--trust-policy",
                str(policy_path),
            ]
        )
        == 0
    )
    assert private_path.read_bytes() == _SIGNING_SEED
    assert not (imported / private_path.name).exists()
