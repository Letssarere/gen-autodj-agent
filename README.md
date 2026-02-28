# 🎧 gen-autodj-agent (Invisible DJ)

> **"비전문가도 누구나 제스처와 목소리로 무대를 장악할 수 있도록"**

**gen-autodj-agent**는 카메라와 마이크 입력을 통해 사용자의 제스처, 표정, 음성을 실시간으로 분석하고, 이를 바탕으로 Ableton Live의 오디오 이펙트와 DJ 무드를 자동 제어하는 **Interactive AI DJ 프로젝트**입니다. 복잡한 DJ 장비나 소프트웨어 지식 없이도 누구나 직관적인 인터랙션만으로 전문가 수준의 다이나믹한 음악 퍼포먼스를 연출할 수 있습니다.

---

## 🌟 핵심 가치 (Core Value)

1. **Intuitive Interaction (직관적 상호작용)**
   마우스나 키보드 조작 없이, 영상(Video)과 음성(Audio), 그리고 텍스트 프롬프트를 통해 사용자의 의도와 현장의 분위기를 즉각적으로 반영합니다.
2. **Real-time Multimodal AI (실시간 멀티모달 AI)**
   **Gemini Multimodal Live API**를 기반으로 오디오 스트림과 카메라 프레임을 지속적으로 분석하여, 현재의 문맥(Context)에 맞는 이펙팅 요소를 결정합니다.
3. **Seamless Ableton Control (매끄러운 Ableton 제어)**
   결정된 AI의 의도는 `set_macro_controls` 함수 호출을 통해 Ableton Live의 매크로 파라미터로 즉시 매핑되며, 보간(Interpolation) 처리를 통해 어색함 없는 자연스러운 음악적 변화를 만들어냅니다.

---

## 🛠 어떻게 동작하나요? (End-to-End Control Flow)

1. **입력 수집 (Input)**
   * **Audio**: Mac 내장 마이크 PCM 스트림
   * **Video**: Mac 내장 카메라 프레임 (JPEG)
   * **Text**: 사용자 지시문 (`--prompt`)
2. **의도 분석 (Gemini Live 추론)**
   * Gemini 모델이 실시간 입력을 분석하고, 분위기에 맞는 DJ 이펙트 값 추론.
   * 실시간 Function Calling을 통해 `filter_macro`, `beat_repeat_macro`, `reverb_macro`, `eq_low_macro` 값을 결정하여 반환.
3. **제어 최적화 및 정규화**
   * AI가 제안한 값을 `[-1.0, 1.0]` 사이의 유효값으로 검증.
   * 부자연스러운 제어를 막기 위한 Deadzone 처리 및 완만한 변화(Ramp) 적용.
4. **Ableton Live 반영**
   * 통신을 통해 Ableton Live 매크로 노브를 실시간으로 조작하여 사운드 직접 변경.

---

## 🎯 기술적 하이라이트 (What We Achieve)

* **에너지 빌드업 (Build-up) & 드랍 (Drop) 연출**: 곡의 전개나 사용자의 제스처/음성 에너지를 감지하여 필터나 리버브를 자동으로 열고 닫는 무드 라이딩 구현.
* **급작스러운 튐 방지 (Smoothing & Neutral Ramp)**: 실시간 추론의 한계인 튀는 값(Jitter)을 방지하기 위해, Hold Time과 Smoothing을 결합한 안정적인 제어 파이프라인.
* **구조화된 AI 제어**: 모델이 자연어 대신 엄격한 함수 호출(Function Calling) 구조로만 제어 값을 응답하도록 디자인하여 예측 가능성 확보.

---

## 📚 문서 및 사용 방법

설치 및 실행 방법, 그리고 자세한 기술 문서는 아래를 참조해 주세요.

* **[🚀 시작하기 (설치, 환경설정 및 실행 가이드)](docs/getting-started.md)** 
* [🧠 아키텍처 원칙 (AGENTS.md)](AGENTS.md)
* [📝 프로젝트 기획 (Project Brief)](docs/project-brief.md)
* [💡 작업 노트 (Working Notes)](docs/working-notes.md)
* [🎛 Ableton Super Rack 설정](docs/ableton-super-rack-setup.md)
