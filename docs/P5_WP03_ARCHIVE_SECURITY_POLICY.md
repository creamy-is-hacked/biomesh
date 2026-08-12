# P5-WP03 Archive Security Algorithm Policy

**Policy version:** 1.0.0

**Envelope schema:** 1

**Status:** approved repository-owned P5-WP03 production profile

## Scope and security boundary

This policy resolves threat-model assumption AS-05 for P5-WP03 only. It wraps
the exact deterministic P4 `.biomesh` bytes; it does not alter the inner ZIP,
its inventory, checksums, project records, execution identity, completed
artifacts, calibration status, plugin policy, registry policy, or queue policy.
Host-owned trust policy remains out of band. No key, credential, trust anchor,
revocation decision, or secret is defined here.

The profile uses the following primary standards:

- Ed25519 as specified by [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032);
- base-mode HPKE and its registered algorithm identifiers/constructions as
  specified by [RFC 9180](https://www.rfc-editor.org/rfc/rfc9180);
- X25519 as specified by [RFC 7748](https://www.rfc-editor.org/rfc/rfc7748);
- HKDF-SHA-256 as specified by
  [RFC 5869](https://www.rfc-editor.org/rfc/rfc5869);
- AES-256-GCM as specified by
  [NIST SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final);
- SHA-256 and SHA-512 as specified by
  [NIST FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final);
- unpadded base64url as the URL-safe alphabet in
  [RFC 4648 Section 5](https://www.rfc-editor.org/rfc/rfc4648#section-5); and
- raw Ed25519/X25519 public-key semantics and PKCS#8/SPKI interoperability as
  specified by [RFC 8410](https://www.rfc-editor.org/rfc/rfc8410).

Python 3.14 is supported through `cryptography>=49,<51`. Version 49 is the
first release providing the RFC 9180 HPKE API used here, and the package's
current PyPI metadata declares Python 3.14 support. P5-WP03 uses only the
library's Ed25519, RFC 9180 HPKE, X25519 raw-key, and serialization APIs.

## Suite registry

Only these exact, case-sensitive suite identifiers are permitted by schema 1:

| Purpose | Suite identifier | Complete profile |
| --- | --- | --- |
| Signature | `BMAS-SIG-1-ED25519` | PureEdDSA Ed25519; 32-octet raw public key; 64-octet signature |
| Confidentiality | `BMAS-ENC-1-HPKE-X25519-HKDF-SHA256-AES256GCM` | RFC 9180 base mode; KEM ID `0x0020` DHKEM(X25519, HKDF-SHA256); KDF ID `0x0001` HKDF-SHA256; AEAD ID `0x0002` AES-256-GCM |

Schema 1 has no `none`, wildcard, alias, compatibility, or inferred suite.
Unknown identifiers fail before cryptographic processing. A later suite needs
a policy-version change, a new identifier, explicit parser/implementation and
tests, and a transition rule. Existing identifiers never change meaning.
Schema or suite transitions are opt-in at the host policy boundary; there is
no negotiation, guessing, fallback, downgrade, or retry under another suite.

## Encodings and identifiers

All security metadata is canonical UTF-8 JSON: object keys sorted, no
insignificant whitespace, one trailing LF, and duplicate keys forbidden.
Binary header values use unpadded base64url and must decode to the exact length
declared below. Non-canonical alternate encodings are rejected.

- Ed25519 and X25519 public keys are their exact 32-octet RFC raw encodings.
- Ed25519 signatures are exact 64-octet RFC encodings.
- HPKE `enc` is the exact 32-octet serialized encapsulated X25519 key. The
  ciphertext is `enc || ct`, where `ct` is the AES-256-GCM ciphertext followed
  by its 16-octet tag as specified by RFC 9180 Sections 7 and 10.
- Private-key storage is host-owned and outside the envelope. The application
  accepts exact 32-octet raw private-key material from an explicit external
  path or an already-loaded key object; it never serializes private keys.
- Key IDs are lowercase hexadecimal SHA-256 values over the exact public key,
  prefixed by `ed25519:` or `x25519:`. The SHA-256 input is respectively
  `BioMesh Ed25519 key id v1\0 || public_key` or
  `BioMesh X25519 key id v1\0 || public_key`.

Logical signer and recipient IDs are separately bound ASCII identifiers. A
logical ID is not a key ID or a trust grant. Host policy must match both the
logical identity and derived key ID to an exact public key.

## Envelope and exact constructions

The outer byte format is:

```text
ASCII "BIOMESH-SECURE-ARCHIVE-V1\r\n"
8-octet unsigned big-endian header length
canonical JSON header bytes
body bytes
```

The header limit is 65,536 bytes. The body must be exactly the declared inner
payload size for plaintext, or that size plus the 32-byte HPKE `enc` and
16-byte GCM tag for confidential content. Truncation, extension,
concatenation, duplicate fields, or non-canonical JSON fails. The header fixes
schema/format, exact payload SHA-256 and size, signature suite/signer/key/replay
metadata, and either the literal `PLAINTEXT` status or the complete HPKE suite,
recipient, recipient key, key/ciphertext encoding metadata.

The Ed25519 signed data is exactly:

```text
ASCII "BioMesh secure archive signature input v1\0"
8-octet unsigned big-endian length of signed_metadata
canonical signed_metadata JSON bytes
8-octet unsigned big-endian payload length
every exact byte of the unsigned P4 archive payload
```

`signed_metadata` is the complete header with the `signature` value omitted;
therefore it binds all algorithm, encoding, signer/key, payload,
confidentiality, and recipient/key metadata. The signature is PureEdDSA
Ed25519 over that complete domain-separated byte string; no external prehash,
Ed25519ctx, or Ed25519ph substitution is allowed.

The replay binding is lowercase SHA-256 over
`BioMesh secure archive replay binding v1\0 || canonical replay fields`. The
replay fields contain the schema, signature suite, signer/key IDs, payload
SHA-256 and size, and complete confidentiality/recipient identity. Host policy
may deny an exact binding and may provide an atomic check-and-record hook. The
hook runs only after authenticated decryption and signature verification and
before P4 parsing or import. BioMesh does not invent a global replay decision;
absence of a host replay restriction is explicit residual policy.

Confidentiality is the RFC 9180 one-shot base-mode operation:

```text
Suite = (DHKEM(X25519, HKDF-SHA256), HKDF-SHA256, AES-256-GCM)
info = ASCII "BioMesh secure archive HPKE info v1\0" ||
       uint64(header_length) || canonical full header
(enc, ct) = SealBase(recipient_public_key, info,
                     aad = empty, plaintext = exact P4 payload)
body = enc || ct
```

The HPKE implementation generates a fresh ephemeral X25519 key from the
operating-system-backed cryptographic RNG for every one-shot encryption and
discards it after use. RFC 9180's labeled KEM/KDF key schedule derives the
32-octet AES key and 12-octet `base_nonce`. BioMesh encrypts exactly one message
per context, so the RFC sequence number is zero and the effective nonce is
`base_nonce XOR I2OSP(0, 12)`. A context is never reused; callers cannot supply
or reuse an ephemeral key, context, sequence, AES key, or nonce. Invalid or
all-zero X25519 shared-secret outcomes fail through RFC 9180 decapsulation.

The full header, including the Ed25519 signature, is HPKE `info`, so every
visible security field participates in the RFC 9180 labeled key schedule and
changed metadata cannot authenticate. The signature binds every plaintext
payload byte and all metadata except its own value. Authenticated HPKE opening
must finish before plaintext identity or signature checking; signature
verification must finish before P4 parsing/import. A valid re-encapsulation of
the same signed plaintext/header has the same replay binding; host replay
policy therefore remains independent of randomized ciphertext bytes.

## Trust, compatibility, and failure policy

Trust records are explicit host-owned mappings of signer ID, derived key ID,
raw public key, allowed suite, active/revoked status, and UTC validity window.
Archive fields never add trust or authorization. Unknown signer, wrong key ID,
revoked key, not-yet-valid key, expired key, unsupported suite/version,
malformed encoding, invalid signature, recipient mismatch, replay rejection,
and authenticated-decryption failure are distinct fail-closed outcomes.
Errors identify the category but never reproduce private material, plaintext,
credentials, ciphertext, tags, or key bytes.

Host trust-policy JSON schema 1 contains exactly `schema_version`, `signers`,
and `prohibited_replay_bindings`. Each signer record contains exactly
`signer_id`, `key_id`, an unpadded-base64url raw `public_key`, UTC
`not_before_utc`/`not_after_utc` timestamps, Boolean `revoked`, and the exact
`allowed_signature_suites` list. Duplicate JSON fields, signer/key bindings,
suites, or replay bindings fail. CLI verification time is current UTC; typed
API callers supply an explicit UTC time for reproducible policy tests.

Signed/plaintext and signed/confidential are independent states. A caller may
require confidentiality in addition to authenticity. Encryption never grants
signer trust, and signing never claims confidentiality. Schema 1 does not
produce unsigned encrypted envelopes.

Raw P4 archives are legacy unsigned input. Verification or import requires the
caller's explicit `ALLOW_UNAUTHENTICATED` policy. A successful legacy import
gets a durable `UNAUTHENTICATED`/`PLAINTEXT` sidecar status; it is never
promoted or backfilled. An authenticated import gets an independently durable
`AUTHENTICATED` and `PLAINTEXT` or `CONFIDENTIAL` status. Inner archive and
completed-run bytes remain unchanged in every case.

P4 checksum/path/size/schema/execution-identity/artifact validation always
runs after security verification and before atomic publication. Secret-like
key files and private-key markers are rejected from signed payloads and
distribution bundles. Authenticity/decryption grants no plugin or registry
trust, execution authorization, calibration status, sandboxing, or scientific
validity.

## Version transitions and residual risks

Readers support schema 1 and the two registered suites only. A future schema
must be selected explicitly by code and host policy; a reader must never
reinterpret schema 1 bytes. Removing a suite requires first prohibiting it in
host policy, then retaining explicit historical rejection/transition behavior
rather than silently mapping it to a replacement.

Residual risks remain the trusted Python/`cryptography`/OpenSSL/OS runtime,
host compromise, private-key custody outside BioMesh, disclosure after
authorized decryption, denial of service within declared limits, and host
replay-store availability. A valid signature authenticates bytes and signer
binding only; it does not establish scientific validity or benign content.
