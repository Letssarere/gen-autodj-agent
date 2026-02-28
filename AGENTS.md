# 🤖 AGENTS.md (System Architecture & Integration Guide)

## 1. Project Vision: "Invisible DJ"
본 프로젝트는 물리적 장비 없이 **Vision(사용자 동작)**과 **Audio(상황 맥락)**를 결합하여 Ableton Live를 실시간 제어하는 AI DJ 시스템입니다. 사용자의 직관적인 퍼포먼스를 DAW의 정교한 파라미터 변화로 치환하는 것이 핵심입니다.

## 2. Core Communication Protocol: OSC (Open Sound Control)
* **Standard:** 모든 데이터 전송은 MIDI가 아닌 **OSC**를 원칙으로 합니다.
* **Ableton Side:** `AbletonOSC` 리모트 스크립트가 11000 포트에서 대기합니다.
* **Python Side:** `pylive` 라이브러리를 사용하여 Ableton의 객체 모델(LOM)에 직접 접근합니다.

## 3. Dual-Layer Control Logic (Hybrid Design)
시스템은 반응 속도와 지능적 판단을 모두 잡기 위해 두 개의 레이어로 분리되어 작동합니다.

### Layer 1: Real-time Kinetic Control (Micro)
* **Source:** MediaPipe (Hand/Pose Landmarks)
* **Characteristic:** 초저지연(Ultra-low Latency) 반영이 필요한 루핑, 필터링 등 '악기적 연주' 담당.
* **Logic:** - 웹캠 프레임(30fps)마다 좌표를 추출하여 특정 파라미터에 직결.
    - 특정 포즈(예: 주먹 쥐기, 특정 위치 손 올리기)를 제어 스위치(Trigger)로 활용.

### Layer 2: Contextual Intelligence Control (Macro)
* **Source:** Gemini Multimodal Live API
* **Characteristic:** 곡의 전체적인 분위기, 에너지 레벨, 사용자 음성 명령 등 '무대 연출' 담당.
* **Logic:** - 비동기적(1~2초 간격)으로 상황을 추론하여 여러 파라미터의 목표 상태(Target State)를 결정.
    - **Smoothing Engine:** AI가 결정한 값은 오디오 튐 현상을 방지하기 위해 파이썬 백엔드에서 부드러운 보간(Interpolation)을 거쳐 전송됨.

## 4. Technical Requirements & Constraints
* **Async Infrastructure:** `asyncio`를 기반으로 Vision, Audio, OSC 루프가 상호 간섭 없이 병렬 실행되어야 합니다.
* **Edge Compatibility:** Ubuntu 22.04 및 Jetson 환경을 고려하여 연산 효율성을 최적화해야 합니다.
* **Zero-Setup Policy:** `AbletonOSC`를 통해 동적으로 파라미터를 탐색하므로, 에이블톤 내에서 개별적인 MIDI 매핑(Cmd+M)은 지양합니다.

## 5. Development Roadmap (Module-based)
1. **`ableton_controller.py`**: `pylive` 기반의 파라미터 읽기/쓰기 및 값 보간 로직.
2. **`vision_engine.py`**: MediaPipe 좌표 추출 및 좌표값의 파라미터 정규화(0.0~1.0).
3. **`ai_agent.py`**: Gemini Live API 연결 및 Function Calling 스키마 정의.
4. **`app_main.py`**: 전체 모듈을 통합하는 비동기 이벤트 루프.