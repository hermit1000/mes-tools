"""Encode one DOB2 MES/CAL file with the shared ADV98 encoder."""

from modules.adv_common.mes_encoder import (
    encode_record_translation,
    leading_quoted_control,
    main,
    normalize_control08_speaker_translation,
    trim_wrap_boundary_spaces,
)


if __name__ == "__main__":
    raise SystemExit(main())
