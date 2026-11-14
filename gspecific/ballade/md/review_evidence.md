# Ballade 리뷰 검증 근거

이 문서는 `C:\work_han\workspace4`의 실제 자료로 확인한 범위와 코드 리뷰에서 철회한 판단을 기록한다. 작업 자료의 위치와 `image-pc98` 산출물의 의미는 `C:\work_han\translation\README.md` 및 `doc/image_conversion.md`를 따른다. 원본 바이너리는 별도 workspace에 있고, `image-pc98`은 디코딩·편집용 중간 자료를 두는 곳이다.

## GPA 프레임 재인코딩

원본 `workspace4/jpn-pc98-dosbox-x/GPA/MAP0INF.GPA`에는 프레임 18개가 있다. `encode_map_inf_gpa.py`의 `frame_offsets`, `decode_frame`, `encode_frame`으로 각 프레임을 메모리에서 디코딩하고 첫째·둘째 행의 픽셀을 하나씩 바꾼 다음 재인코딩·재디코딩했다. 18개 모두 결과 픽셀이 입력과 일치했다. 원본 파일이나 workspace 산출물은 쓰지 않았다.

따라서 `inverse_vertical_xor` 때문에 GPA 프레임이 깨진다는 이전 리뷰 지적은 **철회**한다. 코드의 함수 호출만 보고 디코딩 경로와의 비대칭을 추정한 것은 잘못이었다. 이 검증은 `MAP0INF.GPA`의 수정 픽셀 왕복을 확인한 것이며, 다른 GPA 전체나 게임 화면 표시까지 검증한 것은 아니다.

## 인용 문자열의 이름 매크로

`workspace4/script-pc98`의 `*_info.json` 278개를 살펴보면 `quoted-display` 레코드는 16개, `quoted_macros`가 있는 레코드는 9개다. 예를 들어 `MES/109_3A.MES_info.json`의 `00C5D`와 `00C97`에는 `{이름:クリスティ}` 호출이 있다.

`quoted_display.py`의 `encode_display_quote`는 번역에 있는 이름 토큰이 원본보다 *많은지* 검사한다. 원본에 있던 토큰을 번역에서 생략한 경우는 거부하지 않으므로, 해당 `BA 28` 호출이 결과에서 사라질 수 있다. 이는 실제 레코드가 존재하는 코드 리뷰 지적이다. 필요한 매크로를 반드시 유지할지, 생략을 허용할 예외가 있는지 결정한 뒤 검증 규칙과 테스트를 추가해야 한다.

## 다른 폴더의 이름 정의

같은 278개 info 파일의 `inline_macros`가 참조하는 정의 파일은 현재 `script-pc98` 구조에서 모두 해당 파일의 폴더에 존재했다. `refresh_quoted_names`가 다른 `MARIA.*` 폴더를 검색하지 않는다는 이전 지적은 이 workspace에서 재현되지 않아 **철회**한다. CD 자료 등 다른 폴더 구조를 검토할 때는 그 구조의 파일로 별도 확인해야 한다.

## 관련 문서

같은 폴더의 [Maria_translation_analysis.md](Maria_translation_analysis.md)는
`workspace4`에서 옮긴 인물·대사 번역 판단 자료다. 이미지 코덱과 인용 문자열
인코딩의 검증 근거와는 용도가 다르다.
