# ADV98 GPC stride XOR 검증

검증일: 2026-10-03

## 게임별 실행 루틴

분석 대상 실행 파일의 GPC stride 처리 루틴을 비교했다. 아래 오프셋은 복호화된 실행 이미지 기준이다.

| 게임 | 실행 이미지 | 루틴 오프셋 | 비교한 코드 길이 |
| --- | --- | ---: | ---: |
| Dead of the Brain 1 | `ADVBIOS.EXE.dec` | `0x24C3` | 60바이트 |
| Dead of the Brain 2 | `BRAIN2.OV1.dec` | `0x2825` | 60바이트 |
| Marine Philt | `MARINE.OV1.dec` | `0x2825` | 60바이트 |
| Dracula | `ADVBIOS.OVL.dec` | `0x2787` | 60바이트 |
| Necronomicon | `NECRO.OV1.dec` | `0x30E4` | 64바이트 |

앞의 네 게임에서 비교한 60바이트 루틴은 동일하다. SHA-256은
`546f722c1222ae467270c400b6078c43a8380177bf7aa5255d7a9d6f00d1d2dc`이다.
Necronomicon은 세그먼트 보존과 작업 버퍼 주소 처리가 다르지만, 핵심 XOR 루프 30바이트는 동일하다.
해당 부분의 SHA-256은 `f577c9cd4cae4745d6c13f60ca4a6f5250fc4a1b0c5ad96bcbd1f58f4a24cb15`이다.

이 비교는 나열한 루틴에 한정된다. 실행 파일 전체 또는 모든 이미지 출력 경로가 같다는 뜻은 아니다.

## stride 누적 규칙

첫 체인의 첫 바이트에서 시작한 XOR 누적값은 체인이 끝나도 유지된다.
다음 체인의 첫 바이트 역시 직전 체인의 마지막 복원값과 XOR한다.
체인마다 누적값을 초기화하면 여러 stride에서 잘못된 픽셀이 나온다.

공통 디코더의 `undo_xor_delta()`와 인코더의 `inverse_horizontal_xor()`가 이 순서를 따른다.
`undo_xor_delta_runtime`은 기존 호출을 위한 별칭이다.

## 검증 결과와 적용 범위

복호화된 루틴을 Unicorn 16비트 모드에서 실행하고, `width_bytes=1,2,40,52,80`과
`stride=0,1,2,3,40,80,255`를 조합한 게임별 35개 입력을 비교했다.
체인마다 누적값을 초기화하던 구현은 35개 중 25개가 달랐다.
누적 규칙을 적용한 뒤 다섯 게임의 총 175개 입력에서 불일치가 없었다.
공통 인코더로 다시 만든 GPC도 같은 루틴으로 복원해 175개 입력이 일치했다.

현재 구현은 [`formats/adv98_gpc.py`](formats/adv98_gpc.py)에 있다.
Dracula와 Necronomicon은 캡처 색상에 맞춰 DAC 팔레트 디코더를 선택하며,
Necronomicon의 헤더 변형과 출력 모드 선택은 각각 코덱 옵션과 게임별 도구에서 처리한다.
DOB1의 FRR 보정 옵션은 게임별 인코더에 남아 있다.

저장소의 회귀 테스트는 루트에서 다음 명령으로 실행한다.

```powershell
python -m pytest -q tests/pc98_image
```

실행 파일과 당시의 Unicorn 비교 입력은 저장소에 포함되어 있지 않다.
