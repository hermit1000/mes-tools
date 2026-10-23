# X-Girl PC-98 준비 작업

CD 작업과 번역을 수행하지 않는 X-Girl 전용 준비 도구다.
코드폴더에서 실행한다.

```powershell
python -m gspecific.xgirl.prepare --workspace C:\work_han\workspace1
python -m gspecific.xgirl.configure_environment --workspace C:\work_han\workspace1 --reference C:\work_han\workspace4
python -m gspecific.xgirl.verify --workspace C:\work_han\workspace1
```

실행 파일 분석 자료는 다음 명령으로 준비한다. `unicorn`과 `capstone`이 필요하다.

```powershell
python -m modules.reverse_tools.adv98_dec C:\work_han\workspace1\jpn-pc98\XGIRL.OV1 C:\work_han\workspace1\reverse\XGIRL.OV1.dec
python -m modules.reverse_tools.adv98_dec C:\work_han\workspace1\jpn-pc98\XGIRL.OVL C:\work_han\workspace1\reverse\XGIRL.OVL.dec
python -m modules.reverse_tools.unpack_adv98_runtime C:\work_han\workspace1\reverse\XGIRL.OV1.dec C:\work_han\workspace1\reverse\XGIRL.OV1.raw
python -m gspecific.xgirl.analyze_runtime --workspace C:\work_han\workspace1
```

OV1은 최종 간접 far jump에서, OVL은 고유한 래퍼 꼬리의 RETF 직전에서
에뮬레이션을 중단해 분석용 이미지를 저장한다. 실제 게임 바이너리에 반영하지 않는다.

`prepare`는 기존 출력이 있으면 중단한다. 원본 `jpn-pc98`는 변경하지 않고
`kor-pc98`와 `kor-pc98-dosbox-x`에 동일한 사본을 만든다.
전체 파일의 SHA-256은 `source_manifest.json`에 기록한다.

MES·MEC와 `XGIRL.INI`를 `script-pc98`의 info/lang JSON으로 추출한다.
info에는 원본 해시, 레코드와 전체 토큰 바이트를 보존한다.
모든 토큰의 연속 오프셋과 바이트 단위 원본 복원을 검사한다.
lang의 번역은 빈 문자열로 둔다. 파일별 원문 검토 자료는 `script-review`에 둔다.
공통 ADV98 어휘 분석을 사용하므로 명령 이름, 화자, 외자 및 후보 경계는
X-Girl 실행 코드와 대조하기 전까지 잠정 해석이다. Ballade의 화자 사전,
28칸 제한, 압축 폰트 매핑과 이름 매크로 규칙은 적용하지 않는다.

GPC와 ICON 폴더의 GPC를 모두 추출한다. 이미지 원본, planar·indexed 바이너리,
메타데이터는 `image-pc98/<원본 분류>/<파일명>`에, PNG는 `image-pc98/png`에 둔다.
ICON PNG는 그 아래 `ICON`에 둔다. 파일 크기가 0인 구형 GPC 헤더를 메모리에서만
정규화하고 누적 행 XOR을 복원한다. MES에서 확인되지 않은 출력 모드는 1로 둔다.
원본 바이너리는 그대로 보존한다. 다른 확장자의 데이터는 목록화·복사만 수행한다.

DOSBox-X 설정은 workspace4의 비CD 설정을 사용해 실행 대상을 `XGIRL.COM`으로
바꾼다. 실행기는 현재 폴더로 이동한 뒤 PATH에 있는 `DOSBox-x`를 사용한다.
현재 일본어 원문을 표시하도록 `anex86.bmp`를 사용한다.
`ThinDungGeunMo.bmp`는 향후 작업용으로만 준비하며, 번역과 폰트 재매핑은 수행하지 않는다.

`verify`는 번역 보류 상태에서 사용하는 검사다. 원본과 두 사본의 해시,
스크립트 원본 복원, 빈 번역, GPC 추출 범위와 이미지 크기를 확인한다.
번역을 시작한 후에는 이 명령의 사본 동일성·빈 번역 검사를 그대로 적용하지 않는다.

번역 재삽입, 화자 의미 분석, 폰트 재배치와 특수 자산 디코딩은 별도의
X-Girl 형식 검증을 거쳐 추가해야 한다. 런처 생성은 실제 게임 실행 검증을 뜻하지 않는다.

## 화자 구조 분석

```powershell
python -m gspecific.xgirl.analyze_speakers --workspace C:\work_han\workspace1
```

`speaker-analysis`에 별도 결과를 만든다. 기존 결과가 있으면 중단하며,
info/lang JSON·번역·게임 바이너리는 변경하지 않는다.
독립된 `「名前」` 레코드 + A5와 파일 내부 B9 이름 표시 정의의 BA 호출을
본문에 연결한다. 정의 내부 텍스트는 대사로 세지 않고 AB·AA·분기 경계에서
연결을 끊는다. 파일마다 같은 번호가 다른 이름을 뜻하므로 전역 번호 사전을
사용하지 않는다. 이름 매크로는 가장 가까운 앞선 정의를 사용하며 실행 분기
분석으로 확정된 연결은 아니다. 그룹별 `runtime_verified`는 false로 둔다.

`summary.json`, `groups.json`, `files`, `dialogues-by-file`,
`dialogues-by-speaker`, `unassigned.json`을 생성한다.
미연결 후보에는 지문·UI·어휘 분석이 불완전한 명령 인자도 포함된다.
