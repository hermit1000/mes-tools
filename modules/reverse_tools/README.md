# ADV98 실행 파일 분석 도구

TC0 래퍼 복호화, 16비트 실행 이미지 추출, MZ 또는 raw 코드의 역어셈블을 위한 명령입니다.

```powershell
python -m modules.reverse_tools.adv98_dec INPUT.EXE OUTPUT.EXE
python -m modules.reverse_tools.unpack_adv98_runtime INPUT.EXE OUTPUT.RAW
python -m modules.reverse_tools.disasm_mz16 OUTPUT.RAW --raw
```

`unpack_adv98_runtime`에는 `unicorn`, `disasm_mz16`에는 `capstone`이 필요합니다.
`pip install -e ".[reverse]"`로 함께 설치할 수 있습니다.
