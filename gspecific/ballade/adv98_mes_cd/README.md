# Ballade PC-98 CD

The CD edition is separate from the HD edition. Its 46 `MARIA.000`–`MARIA.045`
containers are sourced from `jpn-pc98-cd/HD/MARIA21`. Their resources and
translation JSON live under the matching container paths in
`jpn-pc98-cd-unpacked` and `script-pc98-cd`.

From the code repository root:

```powershell
python -m gspecific.ballade.adv98_mes_cd.decode_scripts C:\work_han\workspace4
python -m gspecific.ballade.adv98_mes_cd.encode_batch C:\work_han\workspace4
python -m gspecific.ballade.adv98_mes_cd.annotate_hd_matches C:\work_han\workspace4
python -m gspecific.ballade.adv98_mes_cd.repair_ed2_names C:\work_han\workspace4
```

`repair_ed2_names` resolves the CD ED2 name calls using the ID 12/13
definitions in ED3 from the same container, then imports HD translations only
for identical original text and record bytes. It leaves existing CD
translations intact. CD decoding runs this repair automatically.

The annotation command records `hd_match` in each CD `*_lang.json` entry when
its original text and raw record bytes match an HD entry in the same-named
file. It records the HD JSON path, entry ID, and whether the offset or a unique
sequence between neighboring matches resolves repeated text.
`hd_match_candidates` lists IDs if neither check resolves multiple matches.
These fields describe source correspondence,
not whether the translations still agree. Entries with different source bytes
have neither field. Decoding also refreshes these annotations.

For already-created CD JSON, retry only the HD translations held back by
missing inline-token metadata:

```powershell
python -m gspecific.ballade.adv98_mes_cd.repair_reuse C:\work_han\workspace4
```

The retry validates each original-text byte range and name definition against
the CD source, then tests encoding before keeping a translation. Its report is
`script-pc98-cd/token_reuse_repair_report.json`.

`decode_scripts` does not overwrite existing CD JSON. It imports an HD
translation only when the original text has one unambiguous translation in the
same-named HD file. Edit CD JSON independently. `--files 301_18A.MEC` selects
all matching container resources; pass `HD/MARIA21/MARIA.022/301_18A.MEC` to
select one. `--refresh-unpacked` re-extracts original resources.

`encode_batch` writes encoded resources to `kor-pc98-cd-unpacked`, repacks the
original containers, and places only changed files in `kor-pc98-cd/HD`.
`kor-pc98-dosbox-x-cd/HD` is a complete runtime copy of the original HD files
with the changed files overlaid. Failed resources remain original in the repack.
The build report is `kor-pc98-cd/encode_report.json`. `--dry-run` validates
without writing; `--no-repack` updates only unpacked resources.

The build also creates `kor-pc98-cd/FD/Ballade-CD-FD.hdm` from the original CD
boot disk. Only `SHELL21.CNF` and `AUTOEXEC.BAT` are replaced in the image;
the original disk's other content and saves remain intact. The revised
startup command points ADV21 at `C:\MARIA21` and its `MARIA.INI`.
`ballade-pc98-cd.conf` boots the generated floppy as A:, converts the packed
game resource folder into an emulated FAT C: drive at boot, and mounts the
original CD as Q: on the PC-98 secondary IDE master.
