# Stage 1 presentation

The user confirmed on 5 October 2026 (Australia/Sydney) that the
[Drive PPT](https://docs.google.com/presentation/d/1oE-d_TP1XjoBB7gYHby2aZRRSqM9tBBB/edit)
is the actual final PPT.

- [Download the preserved PPT](ReturnOps_Stage1_Video.pptx).
- [Download the preserved A/B/C speaker script](ReturnOps_Stage1_ABC_Script.docx).
- [Open the speaker script in Drive](https://docs.google.com/document/d/1wum-DFCBYcmXA8seB770K_n2R4qxWb7t/edit).
- [Inspect source metadata, checksums and comparison results](source-metadata.json).

## Latest verification — 17 October 2026

Both files were freshly downloaded from the
[shared Drive folder](https://drive.google.com/drive/folders/1bAjQFmkBl-zXthEj2G8a4MybvuaGkfMS).
The existing PPT is byte-identical to the fresh download and has been retained.
The current script, previously linked but not archived, is now included without
editing or re-saving its source bytes.

| File | Current Drive version | SHA256 |
|---|---|---|
| PPTX | 9 slides; 60,493 bytes; modified 22 September 2026, 08:53:27 UTC | `ffc710f5cf2e9c71ed6c433cae2cd5bced7a6c8afaaca74ac672629df2cc484b` |
| Script DOCX | 560 English spoken words; 40,046 bytes; modified 22 September 2026, 09:30:07 UTC | `00006f8132537aa502ff7e2ec1ab65dba1a93bc6c40a6867ce9a6dd142bc1da1` |

Use the DOCX's **English narration** for the shortened rehearsal script, not
the longer PPT notes. Its 7:40 target is a rehearsal plan, not measured video
duration. The script's original report references and historical design-status
wording are preserved; the current repository report is [v0.4](../reports/v0.4/README.md).

The attachments supplied again on 17 October contain the older 55,662-byte PPT
and 48,802-byte / 858-word script from PR #20. That unmerged draft is superseded
here; its original source remains in Git history at
[`a627401`](https://github.com/shuxiachai/returnops-au/tree/a62740166fb6d480fc57edc5256625cb2c3f0b1e/docs/reports/stage1-video-2026-09-21).
The old draft directory is not reintroduced alongside the final archive.

The supplied report PDF is byte-identical to the existing v0.4 PDF. A fresh
Google Docs PDF export has identical page text, decoded page content streams,
page dimensions and embedded image bytes on all 55 pages; its renderer metadata
differs. No report content update is therefore required.

## Historical verification — 5 October 2026

The PPT archive preserves the exact 60,493-byte copy retrieved from that Drive
file on 26 September 2026. Its SHA256 is `ffc710f5cf2e9c71ed6c433cae2cd5bced7a6c8afaaca74ac672629df2cc484b`.
The 5 October check read the Drive file metadata: the source ID, size and last
modification time still match the recorded source. Both raw materialisation
attempts in that task returned HTTP 403 (one for the PPT and one for the script),
so these PPT bytes are not described as a fresh 5 October download or a fresh
content comparison. The user's confirmation identifies the final Drive PPT;
there is no independent comparison with Canvas-uploaded bytes.

The speaker-script link identifies the real Drive document. Its metadata was
checked on 5 October, but a local current copy was not obtained at that time.
The successful 17 October retrieval above supersedes that access limitation;
it does not change the earlier verification record or establish a new Canvas
receipt. Existing historical script material remains separate.

`Video` is part of the original PPT filename. This is a presentation file, not
the recorded video. The user manages the actual recording and submission.
