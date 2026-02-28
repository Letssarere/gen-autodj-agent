# 🤖 AGENTS.md (Architecture Constitution)

## 1. Project Vision: "Invisible DJ"
본 프로젝트는 일반 대중(비전문 DJ)을 대상으로, 카메라/마이크 기반 입력을 해석해 실시간 디제잉 경험을 제공하는 인터랙티브 AI DJ 시스템입니다.

## 2. Hackathon Context & Compliance
* 본 프로젝트는 **Google AI 제품군 활용**을 핵심 평가 포인트로 삼습니다.
* 데모에서는 반드시 **해커톤 기간 중 팀이 직접 구현한 기여**를 명확히 보여야 합니다.
* 해커톤 가이드에 따라 **Streamlit 애플리케이션은 사용하지 않습니다**.

## 3. Execution Environment
* **Device:** Apple MacBook Pro 14 (Apple Silicon M1 Pro)
* **OS/Runtime:** macOS ARM64, Python 3.10+
* **Input Devices:** MacBook 내장 FaceTime 카메라, MacBook 내장 마이크
* **DAW:** Ableton Live 12 (Trial/유료 모두 가능)

## 4. AI + Control Stack
* **Gemini Multimodal Live API (Cloud):** Macro 맥락 추론 + Function Calling
* **MediaPipe (Local):** Micro 제어(후속 단계에서 재통합)
* **Ableton Control:** AbletonOSC + `pylive`

## 5. Current Delivery Phase (Macro-First)
* 현재 전달 단계는 **Macro 우선(Gemini 중심)** 입니다.
* Gemini가 장면/의도 기반 Macro 제어를 생성하고, Python이 smoothing/interpolation 후 Ableton에 반영합니다.
* MediaPipe 기반 즉각 반응형 Micro 제어는 제거가 아니라 **후속 단계로 이연**합니다.

## 6. Control Contract (Frozen)
### 6.1 GeminiMacroControls (외부 계약)
* 모든 입력 값은 `[-1.0, 1.0]` 범위를 사용합니다.
* `0.0`은 중립(의미 있는 변화 최소)을 의미합니다.

### 6.2 BackendNormalizedControls (내부 계약)
* Ableton write 직전 값은 `[0.0, 1.0]` 정규화 범위를 사용합니다.
* 대칭형(symmetric) 타깃 기본식: `n01 = (x + 1.0) / 2.0`
* 원사이드(one-sided) 타깃(`reverb_macro`, `beat_repeat_macro`):
  * `x < 0`이면 `0.0`으로 클램프
  * `x >= 0`이면 `n01 = x`로 매핑
* Deadzone 규칙: `abs(x) < 0.05`이면 중립으로 처리
  * symmetric 타깃 중립값: `0.5`
  * one-sided 타깃 중립값: `0.0`

## 7. Ableton Control Principles
* 제어 프로토콜 표준은 **OSC**입니다.
* Ableton 측은 `AbletonOSC`를 사용하며 기본 포트는 `11000`입니다.
* Python 측은 `pylive`로 LOM(Live Object Model)을 제어합니다.
* 수동 MIDI 매핑(`Cmd+M`) 기반 운영은 기본 경로에서 제외합니다.
* 콘텐츠 셋업(음원 슬롯 배치, 디바이스 최초 로드)은 수동 준비를 기본으로 합니다.
* 퍼포먼스 제어(재생, 정지, 파라미터 조작)는 Python 자동화를 기본으로 합니다.

## 8. Super Rack v1 Baseline (Frozen)
* 기준 트랙: `DJ_MAIN`
* 기준 이펙터 4종: `Auto Filter`, `Beat Repeat`, `Reverb`, `EQ Three`
* 고정 논리 타깃 이름:
  * `filter_macro`
  * `beat_repeat_macro`
  * `reverb_macro`
  * `eq_low_macro`
* 기본 설정 파일은 `config/ableton_targets.json`을 사용합니다.

## 9. Runtime Interface (Current)
* `main.py`는 merged controls를 `control_contract.py`를 통해 `[-1, 1] -> [0, 1]` 변환 후 적용합니다.
* auto-play는 명시적 opt-in입니다.
  * `--auto-play --auto-play-mode clip --auto-play-track 0 --auto-play-slot 0`
  * `--auto-play --auto-play-mode song`

## 10. Verification Commands
```bash
python scripts/list_live_structure.py --max-params 24
python scripts/smoke_pylive.py --targets config/ableton_targets.json --all-targets --value 0.8
python main.py --targets config/ableton_targets.json --auto-play --auto-play-mode clip --auto-play-track 0 --auto-play-slot 0
```

## 11. Document Boundary
* 이 문서는 **확정 원칙**만 다룹니다.
* 미정 아이디어, 실험 항목, 임시 전략은 `docs/working-notes.md`에서 관리합니다.
