# MES 도구

PC-98 게임의 MES 텍스트 추출, 번역 데이터 관리, 재인코딩을 위한 도구 모음입니다.

## 구성

- `modules/adv_common`: ADV98 토큰, ASCII, 문자 인코딩, 패치 공통 코드
- `modules/adv_common/dictionary.py`: 게임별 대사 사전의 공통 집계 및 후보 선택
- `modules/adv_common/mes_*.py`: 공통 MES lexer·decoder·encoder, 배치 실행, 편집용 레코드 생성
- `modules/tools`: 게임별 감사, ASCII 이전, 번역 묶음 도구
- `gspecific/{dob1,dob2,dracula,marine_philt,necronomicon}`: 게임별 MES 구현, 설정 파일 및 보조 도구
- `modules/data/font_table-kor-jin.json`: 패키지에 포함되는 기본 폰트 테이블
- `modules/pc98_image`: PC-98 인덱스 이미지, planar 변환, ADV98 GPC 인코딩·디코딩
- `modules/pc98_image/gpc_usage.py`: MES에서 참조하는 GPC 출력 모드 집계
- `modules/pc98_image/decode_gpc.py`: 공통 GPC 디코딩 CLI와 게임별 경로 프리셋
- `gspecific/<game>/decode_gpc.py` 등: 특수 헤더·팔레트·컨테이너 처리가 필요한 게임별 이미지 도구
- `modules/reverse_tools`: ADV98 실행 파일 분석 도구
- `tests/pc98_image/test_necronomicon_*`: Necronomicon MES 관련 테스트
- `tests/pc98_image/test_*gpc*.py`, `test_planar.py`: 공통 GPC·planar 코덱 검증

게임별 MES 구현은 각 게임의 `adv98_mes/`에 있습니다. `necronomicon/adv98_mes_cd/`에는 CD판의 컨테이너 처리와 MES 도구가 있습니다.

## 참조 관계

| 호출 코드 | 참조 코드 |
| --- | --- |
| `modules/tools/audit_games.py` | `modules.adv_common`의 MES 분석·인코딩 함수 |
| 게임별 `adv98_mes/migrate_ascii.py` | 해당 게임의 JSON 생성기와 `modules.tools.migrate_ascii` |
| DOB1, DOB2, Dracula, Marine Philt, Necronomicon | `modules.adv_common`의 MES lexer·decoder·encoder |
| Necronomicon | 같은 게임의 `system_mec.py`, 공통 `modules/adv_common` |
| Necronomicon CD판 | Necronomicon의 `adv98_mes`, 게임 폴더의 폰트 테이블과 remap JSON |
| 게임별 인코더 | `modules/adv_common`, `modules/data/font_table-kor-jin.json` 또는 게임 폴더의 폰트 테이블 |
| 게임별 GPC 도구 | `modules/pc98_image/formats/adv98_gpc.py`, `modules/pc98_image/adv98_artifacts.py` |

MES 스크립트는 게임 작업공간의 바이너리와 `*_info.json`, `*_lang.json`을 인자로 받습니다. 작업공간 인자를 생략하면 현재 폴더를 사용합니다.

GPC 공통 코덱과 게임별 이미지 도구가 배포 패키지에 포함됩니다. 일부 제목 화면·폰트 생성 스크립트는 `pip install -e ".[image]"`의 추가 의존성이 필요합니다. 실행 파일 분석 도구는 [reverse_tools 안내](modules/reverse_tools/README.md)를 참조하세요. 이전 형식의 pickle 폰트 테이블도 외부 Python 패키지 없이 읽을 수 있습니다.

## 번역 문서

게임별 MES 번역 JSON 편집과 검증에 공통으로 적용하는 기준은 [번역 공통 지침](docs/translation_guidelines.md)에 정리했습니다. 화면 폭, 문자표, 매크로와 상태값은 해당 문서에서 연결한 게임별 지침을 따릅니다.

## 개발 환경

Python 3.10 이상에서 저장소 루트에서 `pip install -e .`로 개발 환경을 설치합니다. 테스트는 `python -m pytest -q`로 실행합니다.

루트에서 모듈 방식으로 실행할 수 있습니다. 예: `python -m gspecific.dob1.adv98_mes.decode_mes --help`.

패키지 경계와 배포 검증 내용은 [구성 문서](docs/architecture.md)에 정리했습니다.
