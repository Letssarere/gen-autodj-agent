# 🤖 AGENTS.md (System Architecture & Integration Guide)

## 1. Project Vision: "Invisible DJ"
본 프로젝트는 별도의 외부 장비 없이 **MacBook 내장 하드웨어**만을 활용하여 사용자의 동작(Vision)과 음성/음악 맥락(Audio)을 분석, Ableton Live를 실시간 제어하는 AI DJ 시스템입니다.

## 2. Hardware & Execution Environment
* **Device:** Apple MacBook Pro 14 (Apple Silicon M1 Pro)
* **Optimization:** M1 Pro의 Neural Engine을 활용한 실시간 비전 처리 최적화 필요.
* **Input Sources:** - **Video:** MacBook 내장 FaceTime HD 카메라
    - **Audio:** MacBook 내장 마이크
* **Runtime:** Python 3.10+ (macOS ARM64 환경)
* **DAW:** Ableton Live 12 (Trial 포함)

## 3. Core Communication Protocol: OSC (Open Sound Control)
* **Standard:** 모든 데이터 전송은 MIDI가 아닌 **OSC**를 원칙으로 합니다.
* **Ableton Side:** `AbletonOSC` 리모트 스크립트가 11000 포트에서 대기합니다.
* **Python Side:** `pylive` 라이브러리를 사용하여 Ableton의 객체 모델(LOM)에 직접 접근합니다.

## 4. Dual-Layer Control Logic (Hybrid Design)
시스템은 반응 속도와 지능적 판단을 모두 잡기 위해 두 개의 레이어로 분리되어 작동합니다.

### Layer 1: Real-time Kinetic Control (Micro)
* **Source:** MediaPipe (Hand/Pose Landmarks)
* **Characteristic:** 0.01초 단위의 즉각적인 필터링, 비트 쪼개기 등 '연주적 타격감' 담당.
* **Logic:** - 내장 웹캠 프레임(30fps)에서 좌표를 추출하여 특정 파라미터에 직결.
    - 특정 제스처(예: 귀에 손 대기, 주먹 쥐기 등)를 이펙터 활성화 스위치(Trigger)로 활용.

### Layer 2: Contextual Intelligence Control (Macro)
* **Source:** Gemini Multimodal Live API
* **Characteristic:** 음성 명령 이해, 전체적인 에너지 레벨 관리 등 '무대 연출' 담당.
* **Logic:** - 내장 마이크를 통해 사용자 명령을 수신하고 비동기적으로 상황을 추론.
    - **Smoothing Engine:** AI가 결정한 목표 값(Target State)은 오디오 튐 방지를 위해 파이썬 백엔드에서 부드러운 보간(Interpolation)을 거쳐 OSC로 전송.

## 5. Technical Requirements & Constraints
* **Async Infrastructure:** `asyncio`를 기반으로 Vision(웹캠), Audio(마이크), OSC 루프가 병렬 실행되어야 합니다.
* **Zero-Setup Policy:** `AbletonOSC`를 통해 동적으로 파라미터를 탐색하므로, 에이블톤 내에서 수동 MIDI 매핑(Cmd+M)은 지양합니다.

## 6. Development Roadmap (Module-based)
1. **`ableton_controller.py`**: `pylive` 기반 파라미터 제어 및 값 보간(Smoothing) 로직.
2. **`vision_engine.py`**: 내장 카메라 기반 MediaPipe 좌표 추출 및 제스처 판별.
3. **`ai_agent.py`**: Gemini Live API 연결 및 Function Calling 정의.
4. **`main.py`**: 전체 모듈을 통합하는 비동기 이벤트 루프 엔트리포인트.