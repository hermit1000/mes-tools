# Ballade GPC 디코딩

코드폴더에서 Conda `base` Python으로 실행한다.

```powershell
python -m gspecific.ballade.decode_gpc --workspace C:\work_han\workspace4
```

원본은 `jpn-pc98/GPC/*.GPC`에서 읽는다. 중간 바이너리와 메타데이터는
`image-pc98/GPC/<원본 파일명>/`, 결과 PNG는 `image-pc98/png/`에 저장한다.
MES의 GPC 지정 명령 및 `COPY` 명령 다음의 `CF` 출력 모드를 파일별로
메타데이터에 기록한다. 기록이 없는 파일은 모드 1을 사용한다. Ballade의
GPC 픽셀은 두 출력 모드 모두 행 XOR을 복원해야 한다.
`--file 001.GPC`로 대상을 고르거나 `--mode 0`/`--mode 1`로
출력 모드를 지정할 수 있다.

## MES·MEC 원문 추출

```powershell
python -m gspecific.ballade.decode_scripts --workspace C:\work_han\workspace4
```

`jpn-pc98/MES`의 `.MES`와 `.MEC`를 읽어 `script-pc98/MES`에
`<원본 파일명>_info.json`과 `<원본 파일명>_lang.json`을 만든다. info에는
원본 해시, 오프셋, 원시 바이트와 전체 디코딩 레코드를 보존하고, lang에는
검토 및 번역할 문자열 후보를 둔다. 기존 JSON을 갱신할 때만 `--force`를
지정한다. 후보는 어휘 단위 추출 결과이므로 재삽입 전에 확인해야 한다.

Ballade에서 `F0` 다음에 압축 가나 바이트가 오면 `F0`은 제어코드로 분리한다.
예를 들어 `512_13.MES`의 `0113B`는 `CONTROL_F0`이고, 대사 `とにかく…`는
`0113C`에서 시작한다. 제어코드는 번역 후보에 포함하지 않는다.

`*_lang.json`의 `speaker_groups`는 `BA 19` 대사 시작 명령을 기준으로
별도 화자 문자열 또는 `B9` 이름 매크로를 본문과 연결한다. 각 그룹에는
`speaker_offset`과 `body_offsets`를 기록한다. 다른 스크립트에서 정의한
이름 매크로는 같은 장의 정의가 한 가지로 일치할 때만 이름을 연결하며,
그렇지 않으면 `speaker_macro_id`만 남긴다.
기존 번역 입력을 유지한 채 그룹 정보만 다시 만들려면 다음을 실행한다.

```powershell
python -m gspecific.ballade.speaker_groups --workspace C:\work_han\workspace4
```

## 번역 전 화자 검토 자료

```powershell
python -m gspecific.ballade.export_speaker_review --workspace C:\work_han\workspace4
```

작업폴더 루트에 화자 목록, 파일 목록, 분석 요청문, 관계·말투 검토표를 만들고
`speaker_dialogues/`에 파일별 대사를 저장한다. 생성된 목록과 대사 파일을
갱신할 때는 `--force`를 사용한다. 직접 채운 관계·말투 검토표는 덮어쓰지 않는다.

## 201_6 이후 업로드용 대사 묶음

```powershell
python -m gspecific.ballade.bundle_speaker_dialogues --workspace C:\work_han\workspace4
```

`speaker_dialogues_grouped_after_201_6/`에 최대 200,000바이트씩 묶은 대사 파일과 `README.md` 색인을 만든다. 화자 미확인 그룹과 본문이 없는 그룹은 제외하고, 각 대사에 원본 파일명과 오프셋을 표시한다. 기존 `speaker_dialogues/` 파일은 변경하지 않는다. 묶음을 다시 생성할 때는 `--force`를 사용한다.

## 번역 사전 생성

```powershell
python -m gspecific.ballade.make_dialogue_dictionary
```

`script-pc98/MES`의 MES·MEC `*_lang.json`에서 원문과 번역을 모아 작업폴더 루트에 `dictionary.json`과 충돌 목록 `annoying.json`을 만든다. 원문 문자열을 정확히 같은 키로 사용하며, 빈 번역도 `""` 후보로 기록한다. 따라서 같은 원문에 번역된 곳과 미번역인 곳이 섞이면 `annoying.json`에서 확인할 수 있다. `{채움}`과 `{글자}`는 인코딩 길이를 맞추는 표기이므로 사전 후보에서는 각각 제거하고 일반 글자로 푼다. 사전을 적용할 때 MES에는 길이 조정 표기를 옮기지 않으며, MEC에서 화면상의 문장이 같은 경우 기존 길이 조정 표기를 유지한다. `@keep`은 원문 유지 후보로 기록한다. 같은 원문에 서로 다른 후보가 있으면 자동 선택하지 않는다. 기존 결과는 기본적으로 덮어쓰며, 이를 막으려면 `--no-force`를 사용한다.
기본 작업폴더는 `C:\work_han\workspace4`이며, 다른 폴더를 쓰려면 `--workspace`로 지정한다.

```powershell
python -m gspecific.ballade.apply_dialogue_dictionary --dry-run
python -m gspecific.ballade.apply_dialogue_dictionary
python -m gspecific.ballade.make_dialogue_dictionary
```

첫 명령은 변경 예상만 출력한다. 두 번째는 기본 실행으로 바로 저장하며, `annoying.json`에서 빈 후보를 빼고 번역이 정확히 하나 남는 원문을 골라 같은 원문의 모든 `lang.json` 항목에 적용한다. 기존 번역이나 `@keep`도 선택한 후보로 덮어쓰며, 이미 후보와 같은 번역은 건너뛴다. 후보가 `@keep`이면 `passed`, 그 외에는 `translated` 상태로 기록한다. `translation_bundles/`가 있으면 같은 항목의 기존 번역도 갱신한다. 번들의 원문·주소 불일치, 중복 또는 누락은 적용 전에 오류를 낸다. 마지막 명령으로 충돌 목록을 현재 `lang.json` 기준으로 갱신한다. 수동 수정한 `annoying.json`은 적용한 뒤에 재생성해야 수정 내용이 보존된다.

## MES·MEC 인코딩 (2바이트 글꼴 코드)

### 번역 문자열 일괄 치환

`replace_translations`는 `script-pc98/MES/**/*_lang.json`의 `entries`를 순회하며
`translation`에서 문자열을 그대로 찾아 바꾼다. 정규식이나 글자별 대응이 아닌
부분 문자열 치환이며, `original`, 주소, 상태 등 다른 필드는 유지한다.
빈 번역과 `@keep`은 건너뛴다. 기본 실행은 변경할 파일 전체를
UTF-8·CRLF로 저장한다.
`--dry-run`을 지정하면 변경 전후와 건수만 보여주고 저장하지 않는다.

스크립트 상단의 `REPLACEMENTS`에 `(찾을 문자열, 바꿀 문자열)`을 지정한 뒤
코드폴더에서 실행한다. 여러 쌍은 위에서 아래로 순서대로 적용한다.

```python
REPLACEMENTS = [
    ("‥‥‥‥‥‥", "……"),
]
```

```powershell
python -m gspecific.ballade.replace_translations
python -m gspecific.ballade.replace_translations --dry-run
```

명령행에 `--replace OLD NEW`를 지정하면 상단 변수 대신 해당 규칙을 사용한다.
여러 번 지정하면 입력한 순서대로 적용한다.
앞 규칙의 결과에도 뒤 규칙이 적용되므로, 겹치는 패턴은 긴 패턴을 먼저 지정한다.
`--workspace`로 작업폴더를, `--lang-dir`로 검색할 JSON 폴더를 바꿀 수 있다.
치환 후 사전 갱신이나 바이너리 인코딩은 자동으로 실행하지 않는다.

Ballade의 외자 `EC65`는 물결 `～`, `EC67`은 닫는 괄호 `」`,
`EC68`은 점 두 개 `‥` 문자로 추출한다.
제어 명령과 ASCII 레코드를 넘지 않는 연속 텍스트는 하나의 레코드로 합친다.
한 글자짜리 텍스트도 번역 후보에 포함한다. 인코딩에서는 `‥`를 `EC68`로,
`…`를 원래 글꼴 코드 `8163`으로 기록한다. `～`와 `~`는 `EC65`,
`」`는 `EC67`로 기록한다. 미확인 외자는 `{외자:EBE9}`처럼 코드로 표시하고
인코딩에서 원래 2바이트로 복원한다. 기존 번역에 없던 원문 조각은
`{원문:00803}`처럼 표시하고 `preserved_text`에 원문·주소·원시 바이트를 저장한다.
이 토큰을 유지하면 원본 바이트를 출력하고, 번역문으로 바꾸면 해당 번역을 인코딩한다.
원문을 보존한 항목은 `incomplete: original text preserved` 상태로 표시한다.
여는 `「`는 BA19 명령에서 출력하므로 번역 문자열에 삽입하지 않고,
info 명령의 `display_prefix`와 lang 대사 그룹의 `opening_quote`에 표시한다.

### A5 줄바꿈과 인코딩 시 공백 처리

`A5`는 info에서 `{줄바꿈:A5}`로 표시하고, 바로 앞 lang 항목의 `layout`에
원문·번역 글자 수와 예상 줄 수를 기록한다. 한 줄 폭은 `text_layout.py`의
`DEFAULT_LINE_COLUMNS = 28`로 지정한다. 원문이 사용하는 줄 수를 기준으로
검사하므로 원문이 두 줄이면 번역에도 두 줄을 허용한다.
닫는 괄호 `」`(EC67)는 표시와 인코딩은 유지하되 글자 폭 계산에서 제외한다.
대사 시작 또는 앞선 A5 등으로 구간 시작을 알 수 있고 문자 폭을 계산할 수 있는
구간만 검증하며, 미확인 외자·위치가 있으면 `unknown_position`으로 표시한다.
인코딩 시 현재 번역으로 다시 계산하므로 JSON에 기록된 검토 수치가 오래되어도
검증은 현재 번역을 따른다. 원문보다 더 많은 줄을 사용하면 `A5 row overflow`
오류로 해당 파일을 저장하지 않는다. 원래 A5 바이트는 유지한다.

인코딩 시 자동 줄바꿈 경계(28글자를 채운 다음)에 오는 공백은 생략한다.
문장 내부의 공백과 JSON의 `translation`은 바꾸지 않는다.
이 처리를 적용한 출력용 문자열로 A5 길이도 검사한다.

```powershell
python -m gspecific.ballade.analyze_text_layout
```

위 명령은 `ballade_a5_layout_review.json`에 현재 번역의 전수 검사 결과를 저장한다.

### 문장 안의 이름 매크로

본문에 삽입되는 이름 호출은 `{이름:패트리샤}`처럼 표시해 앞뒤 문장과 연결한다.
원문에는 `{이름:パトリシア}`처럼 일본어 이름을 표시한다.
info의 `inline_macros`에 매크로 번호, 호출 바이트, 이름 정의 파일·주소와 이름을
보관한다. 인코딩은 토큰 대신 저장된 호출 바이트를 출력한다.
이름 토큰의 누락·중복·잘못된 이름은 오류다. 단, 정의와 번역이 `{외자:EBE9}` 세 개로 된 점 표기 호출은 번역문에서 생략할 수 있다. 이때 해당 BA 호출은 출력하지 않으며 `…` 등을 직접 번역문에 넣을 수 있다.
같은 대사의 텍스트와 A5 줄바꿈으로만 이어진 구간에서는 이름 토큰을 다른 항목으로
옮길 수 있다. 구간 전체의 호출 개수를 검증하고 원래 호출 바이트를 이동한 위치에
출력한다. 명령·대사 종료·경계 코드를 넘어 다른 대사로 옮기는 것은 허용하지 않는다.
원본 info와 번역 JSON은 인코딩에서 변경하지 않는다.
화자 표시용 BA 호출과 대사 시작·종료 명령은 본문으로 합치지 않는다.

인코딩 시 이름 정의의 현재 `translation`을 읽어 실제 출력되는 이름 길이를 계산한다.
28칸 계산은 토큰 표기의 길이를 사용하지 않는다. 이름을 바꾸려면 이름 정의의
번역을 편집한다. 토큰 라벨과 매크로 번호의 연결은 info에 저장되어 있으므로,
토큰 라벨을 임의로 바꾸면 인코딩에서 거부한다.
미확인 외자가 나오기 전까지는 폭을 계산하여 줄 경계 공백을 제거한다.
해당 외자 이후에는 폭을 확정하지 않고 다음 줄바꿈·명령 전까지 공백을 그대로 유지한다.
`merge_special_text --apply`로 외자·단일 글자·이름 호출을 전수 복원할 수 있다.
기존 info/lang은 백업하며, 원본 바이너리는 변경하지 않는다.

기존 번역을 유지하면서 info/lang을 갱신하려면 다음을 실행한다.
기본 실행은 변경 파일 수만 검사하며, `--apply`는 수정 전 파일을
작업폴더의 info/lang 파일을 갱신한다.

```powershell
python -m gspecific.ballade.merge_special_text --workspace C:\work_han\workspace4
python -m gspecific.ballade.merge_special_text --workspace C:\work_han\workspace4 --apply
```

```powershell
python -m gspecific.ballade.encode_mes 000.MES --dry-run
python -m gspecific.ballade.encode_mes 000.MES
python -m gspecific.ballade.encode_batch --dry-run
python -m gspecific.ballade.encode_batch
```

일괄 인코더 `encode_batch.py`는 상단의 `DEFAULT_COMPACT_REMAP`에 지정된
`maria_compact_font_mapping_top67.json`을 기본으로 적용한다.
따라서 별도 인자 없이 실행해도 top67 압축을 사용한다.
다른 매핑은 `--compact-remap`으로 지정할 수 있다.
단일 인코더 `encode_mes.py`는 기존처럼 매핑을 명시할 때 압축을 적용한다.

기본 작업폴더는 `C:\work_han\workspace4`, 기본 글꼴표는 `font_table/font_table-kor-jin.json`이다. `--font-table`로 다른 표를 지정할 수 있다. 기본 결과는 `kor-pc98/MES/`와 `kor-pc98-dosbox-x/MES/` 양쪽에 저장한다. `--output` 또는 `--output-dir`를 지정하면 지정한 한 위치에만 저장한다. `encode_batch.py` 상단의 `DEFAULT_FILES = []`에 파일명을 넣으면 그 파일만 인코딩한다. 빈 목록은 전체 파일을 뜻하며, `--files 000.MES 001.MES`는 설정값보다 우선한다. 선택 실행도 기본 보고서 `kor-pc98/encode_report.json`과 `encode_errors.json`을 해당 실행 대상만으로 갱신한다. 원본 해시·레코드 오프셋·원문을 검증하고, 번역이 비었거나 `@keep`이면 원본 바이트를 유지한다. MES 시작 부분의 저장 장소 제목은 lang JSON 최상위 `graph_op_title.translation`에서 번역한다. `GRAPH_OP @0='…'`의 원문 바이트 길이를 넘지 않게 기록하며, 기존 저장 슬롯의 제목은 게임에서 다시 저장해야 갱신된다. 단일 인코더의 기본 인코딩은 글꼴표의 2바이트 코드만 사용하며, `--compact-remap`을 지정하면 선택한 글자를 1바이트로 바꾼다. 일괄 인코더는 top67 매핑을 기본으로 적용한다. 전각 영숫자·기호는 해당 ASCII 글꼴 이름으로 조회하며, 전각 공백은 일반 공백과 같은 글리프로 처리한다. 원문과 번역이 전각·반각 표기만 다르면 원본 바이트를 유지한다. 글꼴표의 `＝`는 `=`에, `－`는 `-`에, `―`는 `—`에 각각 사용한다.

MEC에서 1바이트로 압축되는 문자 하나를 `{글자}`로 감싸면 원래 글꼴표의 2바이트 코드로 기록한다. 예를 들어 `미사용`이 5바이트이면 `미{사}용`은 6바이트다. 화면에는 같은 세 글자로 표시된다. `{채움}`은 화면에 출력되지 않는 `D6` 명령 1바이트로 기록한다. 예를 들어 `미사용{채움}`도 6바이트이며 화면에는 `미사용`만 보인다. MEC 번역이 원래 대사보다 짧으면 인코딩할 때 부족한 바이트 수만큼 `D6`을 자동으로 덧붙인다. 번역 JSON은 변경하지 않는다. `{채움}`을 직접 넣을 수도 있지만 자동 채움과 중복되지 않도록 필요한 수만 적는다. `00`을 채움 바이트로 넣지 않는다. 메뉴 정렬용 `{반각공백}`은 반각 ASCII 공백 출력 명령 `21 20 00`(3바이트)으로 인코딩하며, 화면에서 8픽셀을 차지한다. MEC에서는 이 3바이트도 대사 길이 제한에 포함된다.

MEC는 각 텍스트 레코드의 최종 바이트 길이가 원본과 정확히 같아야 하며, 긴 번역은 해당 레코드의 원문을 유지한다. MES 결과는 0x3000바이트를 넘지 않아야 한다. ASCII 출력 레코드는 현재 원본 바이트 유지(`@keep` 포함)만 허용한다. 지원하지 않는 글자는 오류로 보고하며, 길이 초과 대사는 원문으로 남긴다. 문장을 자르거나 다른 글자로 바꾸지 않는다. 일괄 실행은 전체 파일을 먼저 검증한 뒤, 기본적으로 통과한 파일만 양쪽 출력폴더에 저장한다. 실패한 파일의 기존 출력은 유지하며, 실패가 있으면 종료 코드는 1이다. `--no-allow-partial`을 지정하면 하나라도 실패할 때 전체 저장을 생략한다. `--dry-run`은 저장하지 않는다. 필요하면 `--files`로 일부 파일만 인코딩할 수 있다. `--manifest-dir`를 지정하면 변경 바이트 구간을 JSON으로 기록한다.

```powershell
python -m gspecific.ballade.analyze_mec_lengths 001_0A.MEC
python -m gspecific.ballade.analyze_mec_lengths 001_0A.MEC_lang.json --output C:\work_han\workspace4\mec_review.json
python -m gspecific.ballade.analyze_mec_lengths
```

파일명을 지정하면 길이가 다른 모든 대사의 원문·번역문·바이트 수를 화면에 표시한다. `--output`을 지정하면 JSON으로도 저장한다. 파일명을 생략하면 `kor-pc98/encode_report.json`의 원문 유지 MEC를 검사해 `ballade_mec_length_review_top67.json`에 저장한다. 일괄 인코딩을 실행하면 긴 대사의 원문 유지 위치만 `mec_original_fallbacks`에 기록한다. 짧은 대사의 자동 채움 내역은 기본 보고서에서 생략한다. 전체 인코딩의 기본 보고서는 `kor-pc98/encode_report.json`이다. 길이 초과로 원문을 유지한 MEC 대사 목록(`mec_original_fallbacks`)만 `kor-pc98/encode_errors.json`에 따로 기록한다. `--report`를 지정하면 이 목록은 같은 폴더의 `<보고서명>_errors.json`에 기록한다.

## top67 매핑 만들기

현재 번역의 실제 글자 빈도로 67개 압축 코드를 배정합니다. 이름·외자·원문 토큰은 집계에서 제외합니다. 매핑을 바꾸면 글꼴 BMP를 다시 만들고 MES/MEC를 재인코딩해야 합니다.

```powershell
python -m gspecific.ballade.build_compact_mapping_top67
python -m gspecific.ballade.build_compact_font
python -m gspecific.ballade.encode_batch
```

## top67 글꼴 BMP 만들기

```powershell
python -m gspecific.ballade.build_compact_font
```

작업폴더의 `ThinDungGeunMo.bmp`에서 67개 원본 글리프의 16×16 픽셀을 복사해
`ballade-ThinDungGeunMo.bmp`를 만든다. 압축 코드 `2D`~`6F`에 대응하는
Shift-JIS 글리프 칸만 교체한다. 결과는 원본과 같은 2048×2048 1비트 BMP이며,
`font_table-kor-jin-ballade-compact-top67.json`에 변경된 코드 대응을 기록한다.
