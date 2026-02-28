# Ableton Super Rack Setup Guide (v1)

## 1. 목적
이 문서는 Macro-First 단계에서 필요한 Ableton 수동 준비 절차와 실행 검증 절차를 표준화합니다.
대상은 `DJ_MAIN` 트랙 1개와 Super Rack v1(4이펙터) 구성입니다.

## 2. 사전 조건
* Ableton Live 12 실행 가능
* AbletonOSC 설치 및 Control Surface 활성화(기본 포트 `11000`)
* Python 환경에서 `pylive` 사용 가능

## 3. DJ_MAIN 트랙 준비
1. 새 Live Set을 열고 필요한 트랙만 남깁니다.
2. 메인 오디오 트랙 이름을 `DJ_MAIN`으로 지정합니다.
3. Device View(`Shift+Tab`)에서 `Drop Audio Effects Here` 영역을 확인합니다.

## 4. Super Rack v1 구성
1. `Audio Effect Rack`을 `DJ_MAIN`에 삽입합니다.
2. Rack 내부에 아래 순서로 이펙터를 삽입합니다.
   * `Auto Filter`
   * `Beat Repeat`
   * `Reverb`
   * `EQ Three`
3. 사용하지 않는 기본 상태를 위해 이펙트 양/스위치를 중립값으로 저장합니다.

## 5. 매크로 매핑 기준
권장 논리 타깃과 Rack 매크로 매핑은 아래를 사용합니다.

| Logical Target | Rack Macro | 기본 의미 |
|---|---:|---|
| `filter_macro` | Macro 1 | 주파수 톤 이동(대칭형) |
| `beat_repeat_macro` | Macro 2 | 반복/글리치 양(원사이드) |
| `reverb_macro` | Macro 3 | 공간감 양(원사이드) |
| `eq_low_macro` | Macro 4 | 저역 밸런스(대칭형) |

추가 권장:
* 각 이펙터 Device On/Off를 별도 매크로(예: 5~8)에 연결
* 기본 저장 상태는 neutral 기준(청감상 변화 최소)

## 6. 제어 계약
### 6.1 Gemini 출력 (외부)
* `GeminiMacroControls`: `[-1.0, 1.0]`
* `0.0`: 중립
* Deadzone: `abs(x) < 0.05`

### 6.2 Ableton 적용 전 변환 (내부)
* `BackendNormalizedControls`: `[0.0, 1.0]`
* 대칭형 타깃(`filter_macro`, `eq_low_macro`): `n01 = (x + 1.0) / 2.0`
* 원사이드 타깃(`reverb_macro`, `beat_repeat_macro`):
  * `x < 0` -> `0.0`
  * `x >= 0` -> `n01 = x`

## 7. 템플릿 저장
1. 세팅 완료 후 `File -> Save Live Set As...`
2. 예시 파일명: `Super_DJ_Template.als`
3. 데모/테스트 시작 시 템플릿을 먼저 열어 구조 일관성을 유지합니다.

## 8. 세션 시작 체크리스트
1. Ableton Live 실행 + AbletonOSC 활성 상태 확인
2. `Super_DJ_Template.als` 열기
3. 사용할 클립을 Session 슬롯에 수동 배치
4. Python 환경 활성화
5. 구조 확인/검증 실행

```bash
python scripts/list_live_structure.py --max-params 24
python scripts/smoke_pylive.py --targets config/ableton_targets.json --all-targets --value 0.8
```

## 9. main.py auto-play 모드
`main.py`는 auto-play를 명시적으로 켠 경우만 재생 트리거를 호출합니다.

### 9.1 clip 모드
* 의미: 지정한 track/slot 클립을 직접 launch
* 예시:

```bash
python main.py \
  --targets config/ableton_targets.json \
  --auto-play \
  --auto-play-mode clip \
  --auto-play-track 0 \
  --auto-play-slot 0
```

### 9.2 song 모드
* 의미: Ableton 글로벌 재생(start_playing)
* 예시:

```bash
python main.py \
  --targets config/ableton_targets.json \
  --auto-play \
  --auto-play-mode song
```

## 10. 재캘리브레이션 절차(구조 변경 시)
1. Live Set 구조 변경(트랙/디바이스/파라미터)이 있었는지 확인
2. `list_live_structure.py` 출력으로 인덱스 재확인
3. `config/ableton_targets.json`과 `config/ableton_targets.super_rack_v1.example.json`을 동일 스키마로 유지
4. `smoke_pylive.py` 재실행으로 write/read 검증

## 11. 자동화 경계 요약
* 자동화 가능: 재생, 정지, 템포, 파라미터 제어, safe reset
* 수동 필요: 음원 import/배치, 디바이스 최초 삽입, 템플릿 관리
