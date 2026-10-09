# Necronomicon PC-98 CD 빌드 도구

기존 `adv98_mes` 코덱과 폰트표를 사용합니다. CD 컨테이너의 이름·위치·메타데이터를 보존하고, 파일 길이가 달라지면 위치와 전체 크기를 갱신합니다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `jpn-pc98-cd/FD`, `HD` | 원본 부팅 파일과 컨테이너 |
| `jpn-pc98-cd-unpacked/HD` | 컨테이너별 원본 리소스 |
| `script-pc98-cd/HD` | info/lang JSON |
| `kor-pc98-cd-unpacked/FD`, `HD` | 한글 리소스와 수정한 부팅 설정 |
| `kor-pc98-cd/FD`, `HD` | 재패킹 결과와 부팅 이미지 |
| `kor-pc98-dosbox-x-cd/FD`, `HD` | Neko 실행 데이터 |

## JSON 생성 및 기존 번역 재사용

저장소 루트에서 실행합니다.

```powershell
python -m gspecific.necronomicon.adv98_mes_cd.decode_mes C:\work_han\workspace1
```

원본 추출 목록이 없으면 컨테이너를 먼저 추출합니다. 현재 한글 MES와 기존 번역 JSON을 대조한 뒤 같은 원문 또는 같은 원본 바이트의 번역을 가져옵니다. 현재 한글 MES와 JSON이 다른 단순 텍스트 구간은 실제 MES의 표현을 복원합니다. 기존 CD 번역은 보존합니다.

`--files MAIN.MES`로 파일을 선택할 수 있습니다. `--no-reuse`는 기존 번역 가져오기를 끕니다. `--output`은 JSON 출력 폴더를 지정합니다. `--refresh-unpacked`는 원본 컨테이너를 다시 추출합니다.

CD 음악 명령 `D0 cd`는 명령 인수로 처리합니다. 잘못된 `ぷへ` 후보를 만들지 않습니다. 컨테이너 안의 중복 파일명은 `_duplicates/항목번호`에 보존합니다.

## 전체 인코딩·재패킹·실행 데이터 갱신

```powershell
python -m gspecific.necronomicon.adv98_mes_cd.encode_mes_batch C:\work_han\workspace1 --jobs 4
```

Neko를 종료한 뒤 실행합니다. 모든 인코딩을 임시 폴더에서 검증한 후 결과 폴더를 갱신합니다. 원문 바이트, 패치 범위, 번역 JSON 해시, MES 크기를 검사합니다. 기존 한글 이미지와 선택하지 않은 한글 MES를 유지하며 컨테이너를 재패킹합니다.

`--files MAIN.MES` 또는 `--files HD/NECRO/NECRO.008/MAIN.MES`로 부분 빌드할 수 있습니다. `--no-dosbox-x` 또는 `--no-runtime`은 실행 데이터 갱신을 생략합니다. `--font-table`, `--compact-remap`, `--no-compact-remap`도 지원합니다.

한 파일은 `encode_mes.py source info lang output`으로 인코딩합니다.

## 이미 인코딩한 이미지·리소스만 재패킹

```powershell
python -m gspecific.necronomicon.adv98_mes_cd.repack_containers C:\work_han\workspace1 --deploy
```

`--deploy`를 빼면 두 작업 결과 폴더만 사용하고 Neko 실행 데이터를 갱신하지 않습니다.

## 부팅 설정

`kor-pc98-cd-unpacked/FD`의 `AUTOEXEC.BAT`, `SHELL21.CNF`, `HOSTDRV.COM`을 수정하고 아래 명령으로 부팅 이미지를 갱신합니다.

```powershell
python -m gspecific.necronomicon.adv98_mes_cd.build_boot_disk C:\work_han\workspace1
```

플로피의 다른 파일과 기존 세이브는 보존합니다. 전체 빌드는 부팅 이미지와 실행용 복사본도 갱신합니다.

## 실행 구성

- `necronomicon-pc98-cd-runtime/run-necronomicon-cd.bat`: 기본 실행. 원본 플로피와 원본 CD만 사용하고 HOSTDRV는 끕니다.
- `run-original-cd-only.bat`: 같은 원본 CD 전용 비교 실행.
- `run-korean-hdd.bat`: 별도의 한글 시험 실행. HOSTDRV의 C:에 번역 컨테이너를 연결하고 원본 CD 음악을 사용합니다.

빌드는 기본 원본 CD 전용 설정을 변경하지 않습니다. 보고된 어린정 이후의 HOSTDRV 일본어판 멈춤은 원본 CD 전용 구성과 별도로 비교해야 하며, 번역 빌드가 이 문제를 해결했다고 검증된 상태는 아닙니다.
