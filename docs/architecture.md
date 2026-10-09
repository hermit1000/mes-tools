# MES 저장소 구성 제안

## 현재 경계

| 영역 | 책임 | 권장 위치 |
| --- | --- | --- |
| 공통 코덱 | ADV98 토큰, ASCII, 문자 코드, 패치, 대사 사전 후보 집계 | `modules/adv_common/` |
| 공통 MES 작업 | lexer, decoder, encoder, 배치 실행, 편집용 레코드 생성 | `modules/adv_common/mes_*.py` |
| 공통 작업 도구 | 감사, 번역 묶음, ASCII 이전 비교 | `modules/tools/` |
| 게임별 ASCII 이전 CLI | 해당 게임의 JSON 생성기 연결 | `gspecific/{dob1,dob2}/adv98_mes/migrate_ascii.py` |
| 게임별 어댑터 | 각 게임의 레코드 구조, 제어 코드, 인코딩 제약, 설정 JSON | `gspecific/<game>/adv98_mes/` |
| CD판 컨테이너 | Necronomicon CD의 추출·재포장·실행 환경 | `gspecific/necronomicon/adv98_mes_cd/` |
| 공통 이미지 코덱 | 인덱스 이미지, planar 변환, ADV98 GPC, PNG 저장 | `modules/pc98_image/` |
| GPC 사용 정보 | MES 명령에서 파일별 출력 모드 집계 | `modules/pc98_image/gpc_usage.py` |
| 게임별 이미지 도구 | 게임별 출력 모드, 팔레트, 파일 목록, 제목 화면 | `gspecific/<game>/` |

대사 사전의 원문별 후보 집계와 단일 후보 선택은 `modules/adv_common/dictionary.py`로 모았습니다. DOB1의 사전에는 별도의 `keep` 필드가 있어 생성 로직은 게임 폴더에 유지합니다. Marine의 연결 대사는 `combined_original`과 `@keep` 규칙을 적용한 다음 공통 집계 함수를 호출합니다. 빈 번역을 후보 충돌로 볼지 여부는 호출부가 지정합니다.

## 코드 리뷰 결과

1. `modules/tools/audit_games.py`의 상대 import가 잘못된 패키지를 가리켰고, `modules/tools/translation_bundles.py`는 `python -m` 실행 시 import에 실패했습니다. 두 경로는 수정했습니다.
2. Necronomicon CD 패키지에는 하드코딩된 외부 경로 fallback이 있었습니다. 현재 저장소를 기준으로 참조하도록 변경했습니다.
3. `gspecific/necronomicon/adv98_mes/annotate_display_groups.py`에는 끝나지 않은 `if` 블록이 있었습니다. 문법을 복구했지만 번역문 줄 맞춤 규칙은 실제 샘플로 추가 검증이 필요합니다.
4. 공통 GPC 코덱은 `modules/pc98_image/`에, 게임별 이미지 도구는 `gspecific/`에 있습니다. 실행 파일 분석 도구는 `modules/reverse_tools/`에 있습니다.
5. 게임 작업공간의 기본값은 현재 폴더로 통일했습니다. 자동 실행 시에는 의도한 작업공간에서 실행하거나 경로 인자를 명시해야 합니다.
6. 기본 폰트 테이블은 `modules/data/`에 패키지 데이터로 포함하고, `modules.resources.default_font_table()`로 경로를 결정합니다. 게임별 폰트 테이블은 각 게임 패키지에 보관합니다.
7. 이전 pickle 폰트 테이블의 `module.font_table.FontTable` 참조는 공통 코드에서 호환 처리합니다. JSON이 기본 입력입니다.

## 검증 및 다음 정리 순서

1. 게임별 MES 디코더와 인코더를 실제 파일 쌍으로 왕복 검증하고 공통 구현의 포맷 호환성을 확인합니다.
2. 테스트는 공통 사전, 폰트 테이블, Necronomicon MES, GPC 인코딩·디코딩, planar 변환을 확인합니다. 실제 게임 바이너리는 포함하지 않습니다.
3. wheel에 기본 폰트 테이블, 공통 GPC 코덱, 게임별 이미지 도구를 포함합니다. 분리된 폴더에서 GPC 왕복 인코딩과 게임별 래퍼 import를 확인했습니다. Python import 이름은 `modules`와 `gspecific`입니다.
