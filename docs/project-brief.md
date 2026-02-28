# Project Brief: gen-autodj-agent

## 1. 문제 정의와 타깃 사용자
디제잉은 장비 비용과 학습 난이도가 높아 일반 사용자가 접근하기 어렵습니다.  
`gen-autodj-agent`는 비전문 사용자도 카메라/마이크와 대화형 AI만으로 분위기를 조절할 수 있는 실시간 DJ 보조 시스템을 목표로 합니다.

## 2. 솔루션 개요 (Current Macro-First)
현재 해커톤 전달 단계는 **Gemini 기반 Macro 제어 우선**입니다.
* 입력: 화면/음성/프롬프트 맥락
* 추론: Gemini Multimodal Live API가 장면 의도를 해석해 제어값 생성
* 제어: Python 백엔드가 `control_contract`를 통해 `[-1,1]`을 `[0,1]`로 변환 후 AbletonOSC + `pylive`로 반영

참고:
* Gemini 출력 계약: `[-1.0, 1.0]`, `0.0 = 중립`
* Ableton 적용 계약: `[0.0, 1.0]` 정규화값

## 3. 데모 스토리 (Macro-First Pitch)
1. 사용자가 음성/텍스트로 현재 무드(예: "빌드업", "차분하게")를 지시합니다.
2. Gemini가 맥락을 해석해 Macro 제어값(`-1.0~1.0`)을 반환합니다.
3. 백엔드가 안전한 범위로 보간 후 Super Rack 매크로에 반영합니다.
4. Auto Filter/Beat Repeat/Reverb/EQ Three가 조합되어 곡 분위기가 자연스럽게 변합니다.

## 4. 자동화 경계 (운영 원칙)
### 4.1 수동 준비(콘텐츠 셋업)
* 음원 파일을 Session 슬롯에 배치
* `DJ_MAIN` 트랙과 Super Rack(4이펙터) 구성
* AbletonOSC 활성화 및 템플릿(`.als`) 저장

### 4.2 자동화 가능(퍼포먼스 제어)
* 재생/정지/씬 및 클립 트리거
* 템포/볼륨/파라미터 실시간 제어
* Macro 제어값 smoothing 및 안전 복귀

## 5. Quick Validation
```bash
python scripts/list_live_structure.py --max-params 24
python scripts/smoke_pylive.py --targets config/ableton_targets.json --all-targets --value 0.8
python main.py --targets config/ableton_targets.json --auto-play --auto-play-mode clip --auto-play-track 0 --auto-play-slot 0
```

## 6. In-scope / Out-of-scope
### In-scope (현재 라운드)
* Super Rack v1(4이펙터) 기준 기본 실행 경로 전환
* Macro 제어 계약(`-1~1 -> 0~1`) 코드/설정/테스트 동기화
* auto-play 옵션 기반 실음원 테스트 지원
* Gemini Live 오디오+비디오+텍스트 입력 및 Tool Calling 기반 Macro 제어 실구현
* 세션 내구성(재연결, session resumption handle 반영, go_away 처리) 적용

### Out-of-scope (후속 라운드)
* MediaPipe Micro 제어 루프 실구현
* 런타임 오케스트레이션 대규모 리팩터링
* Gemini AUDIO 출력(스피커 재생) 경로 통합
