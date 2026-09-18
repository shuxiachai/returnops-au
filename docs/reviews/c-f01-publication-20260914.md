# C-F01 contract-test correction publication — 2026-09-14

The commit containing this notice publishes the C-F01 correction and its
[technical review snapshot](pr12-followup-20260914.md) with the
[verification receipt](pr12-followup-20260914.json) through
[PR #11](https://github.com/shuxiachai/returnops-au/pull/11).
The review source before this follow-up was
`64582a3007fea0fa3d1b1c3c212168b96af6b607`; product/wire candidate rc.5 remains
unchanged. C's reviewed PR #12 head remains
`68e5e4b6569508c1988fa099eabbec8222ea5c0b`.

Only the historical-bundle test oracle/fixtures and these three review records
are included. Exact proposal ID/version and one-to-one citation coverage are
checked; historical non-VALID results and zero-citation records remain legal.
No schema, runtime or existing member source is changed.

## Reading the evidence

The linked review and JSON are retained pre-publication snapshots. Their
local/uncommitted wording refers to that inspection, and their raw-file hashes
are local-byte hashes. The 18 model-tool regressions in that snapshot included
the separate unpublished checker changes. This publication uses the existing
committed checker with 12 regressions. The F.03 component, dependency/CI changes
and full team report remain outside this commit and its CI coverage.

An isolated checkout containing exactly this publication was checked using the
existing Python environment and installed locked Mermaid dependencies; no fresh
installation, HTTP/database or member reproduction is claimed by that local run.
Validation results are recorded in the PR against the resulting exact commit.
The original rc.5 publication manifest remains a historical manifest of rc.5,
not a hash list for the subsequently corrected test file.

## Review boundary

The bounded C-F01 test finding is locally corrected and independently reviewed.
Publication is not C's follow-up confirmation, a personal signature, F.01/F.02
joint acceptance, merge authorization or course submission. Keep PR #12 and B's
PR #8 separate while their exact-source integration and review remain open.
The actual new source and CI links are recorded in PR #11; do not substitute
old rc.5 or PR #12 checks for this commit's own checks.
