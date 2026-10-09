# MES 번역 공통 지침

이 문서는 `*_lang.json`으로 ADV98 MES를 번역할 때 여러 게임에 공통으로 적용하는 기준이다. 실제 필드 구조, 화면 폭, 문자표, 매크로, `status` 값과 `@keep` 지원 여부는 아래 게임별 문서를 우선한다.

| 게임 | 세부 지침 |
| --- | --- |
| Dead of the Brain 1 | [번역 규칙](../gspecific/dob1/adv98_mes/TRANSLATION_GUIDELINES.md) |
| Dead of the Brain 2 | [MES 작업과 번역 형식](../gspecific/dob2/adv98_mes/README.md) |
| Dracula | [번역·인코딩 규칙](../gspecific/dracula/TRANSLATION_RULES.md) |
| Marine Philt | [번역 지침](../gspecific/marine_philt/adv98_mes/TRANSLATION_GUIDELINES.md) |
| Necronomicon | [번역 규칙](../gspecific/necronomicon/TRANSLATION_RULES.md) |

## 번역 JSON 편집

- 원문과 번역문이 같은 레코드를 가리키는지 `id`와 `offset`으로 확인한다. 게임별 지침에서 허용한 편집 필드만 수정하고 `original`, `id`, `offset`, 원본 바이트와 소스 정보를 보존한다.
- 여러 레코드에 걸친 문장은 앞뒤 원문을 함께 읽는다. 레코드 사이에 텍스트가 이어지는 방식과 분할 표식은 게임별 규칙을 따른다. 레코드를 임의로 합치거나 순서를 바꾸지 않는다.
- 같은 인물과 장소는 파일 전체에서 같은 이름으로 표기한다. 게임별 화자 사전과 고유명사 표기를 확인하고, 의미를 유지하면서 자연스러운 한국어로 다듬는다.
- 번역문에 쓰는 문자는 해당 게임의 폰트 테이블과 인코더가 처리할 수 있어야 한다. 원문과 동일한 바이트 길이로 맞추려 하지 말고, 게임별 화면 폭과 레코드 용량을 확인한다.

## 문장부호와 공백

- DOB1, Dracula, Marine Philt, Necronomicon의 MES 번역문에서는 `.`와 `,` 뒤에 일반 공백을 넣지 않는다. 이 규칙을 다른 게임의 모든 텍스트 형식에 그대로 적용하지 않는다.
- `?`, `!`, 말줄임표 뒤에 새 문장이 이어질 때는 읽기 위한 공백을 둔다. 문장 끝, 줄 또는 레코드 경계에 의미 없는 후행 공백을 남기지 않는다.
- 문장부호가 화면의 새 줄 첫 칸에 홀로 남거나 말줄임표가 어색하게 끊기지 않도록 번역문을 조정한다. 인코더가 처리하는 줄 경계 공백과 의도한 들여쓰기는 게임별 규칙을 따른다.
- DOB1의 `{.}` 같은 매크로와 Marine Philt의 `{next}`는 단순 문장부호가 아닌 구조 표식이다. 각 게임 문서의 보존·이동 규칙을 따른다.

## 원문 유지와 검증

- 원문을 그대로 두는 방법은 게임마다 다르다. DOB2, Dracula, Marine Philt, Necronomicon에서 쓰는 `@keep`을 DOB1에 적용하지 않는다. 빈 번역과 `@keep`도 같은 뜻으로 취급하지 않는다.
- `status`는 게임별 검증 흐름에 맞춰 설정한다. `translated`와 `passed`의 의미를 임의로 통일하지 않는다.
- 번역 검토 때 화자·고유명사, 레코드 대응, 구조 표식, 후행 공백과 화면 폭을 확인한다. 인코딩 단계에서는 해당 게임의 도구로 MES 생성과 원본 바이트 보존을 검증한다. 인코딩 시점은 게임별 작업 절차를 따른다.
