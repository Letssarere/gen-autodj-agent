# Working Notes (Experimental / Open Items)

## 1. Decision Log (확정 결정사항)
1. Ableton 제어는 `AbletonOSC + pylive`(OSC)로 통일한다.
2. 실행 환경은 MacBook Pro 14 (M1 Pro) + macOS ARM64 + Python 3.10+를 기본으로 한다.
3. 입력 장치는 MacBook 내장 카메라/마이크를 사용한다.
4. 현재 전달 단계는 Macro-First로 운영하며 Gemini 중심 제어를 우선한다.
5. 기본 타깃은 Super Rack v1 4종(`filter_macro`, `beat_repeat_macro`, `reverb_macro`, `eq_low_macro`)으로 고정한다.
6. Gemini 제어값 계약은 `[-1.0, 1.0]`, `0.0 = 중립`으로 고정한다.
7. Ableton write 직전 값은 `[0.0, 1.0]`로 정규화한다.
8. 원사이드 타깃(`reverb_macro`, `beat_repeat_macro`)은 `x < 0` 시 `0.0`으로 클램프한다.
9. Deadzone은 `abs(x) < 0.05` 규칙을 사용한다.
10. `main.py`는 auto-play를 명시적 opt-in 옵션으로 제공한다.
11. 수동 MIDI 매핑(`Cmd+M`)은 기본 운영 경로에서 제외한다.
12. Gemini Tool Calling 계약은 `set_macro_controls` + 4개 고정 타깃 필드 + `additionalProperties=false`로 고정한다.
13. Gemini Live 장애 폴백은 `2초 hold + 1초 neutral ramp`를 기본으로 한다.

## 2. Open Questions (미정 항목)
1. Macro 시나리오별 우선 액션 정책 (미결)
   - 예: 빌드업/브레이크다운/드롭 전환 시 파라미터 우선순위
2. Live 세트 템플릿 버전 정책 (미결)
   - `.als` 템플릿 변경 시 config 버전 동기화 방식
3. MediaPipe 재통합 시 인터럽트 정책 (미결)
   - Macro 적용 중 Micro override 허용 범위

## 3. Experiment TODO
1. 레이턴시 측정 기준 수립 및 계측
   - Gemini 응답 시점 → Ableton 파라미터 반영 시점
2. Smoothing 파라미터 튜닝
   - 반응성(빠름) vs 안정성(아티팩트 최소화) 균형점 찾기
3. 데모 안정성 체크리스트 작성
   - 네트워크 지연, API 재시도, Ableton 연결 복구, safe reset

## 4. Risks / Mitigations
1. 네트워크 지연(Cloud API)
   - 완화: rate limit + smoothing + fallback neutral
2. 오디오 아티팩트(급격한 파라미터 점프)
   - 완화: interpolation, clamp, deadzone
3. 세트 구조 변경으로 인덱스 mismatch
   - 완화: `scripts/list_live_structure.py` 재캘리브레이션 후 smoke test
4. clip auto-play 실패(빈 슬롯/인덱스 오류)
   - 완화: `--auto-play-mode song` 폴백 또는 track/slot 재설정

## 5. Verification Commands
```bash
python scripts/list_live_structure.py --max-params 24
python scripts/smoke_pylive.py --targets config/ableton_targets.json --all-targets --value 0.8
python main.py --targets config/ableton_targets.json --auto-play --auto-play-mode clip --auto-play-track 0 --auto-play-slot 0
```

## 6. Notes for Next Iteration
* MediaPipe Micro 루프는 Macro-First 안정화 이후 단계적으로 재통합한다.
* Open Questions가 닫히면 해당 결정사항은 `AGENTS.md`로 승격하고 이 문서는 히스토리 중심으로 유지한다.
