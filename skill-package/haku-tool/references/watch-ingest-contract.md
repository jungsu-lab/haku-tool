# `/watch` evidence ingest contract

영상 URL이나 로컬 영상을 Haku 분석에 넣기 전에 다음 계약을 적용한다.

1. 소스를 `owned`, `licensed`, `permissioned-analysis`, `public-reference-only` 중 하나로 판정한다. `unknown`이면 중단한다.
2. Windows 작업공간에서는 `C:\Users\HP-5600G\Desktop\AI 제작과정\tools\run-watch.cmd`를 사용한다.
3. 기본 호출은 외부 전사를 금지한다. 사용자가 음성 업로드를 명시적으로 허용한 경우에만 `-AllowExternalTranscription`을 쓴다.
4. 경로에 한글이나 공백이 있어도 원문 경로를 그대로 인자로 전달한다.
5. `/watch`가 나열한 프레임을 주 에이전트가 모두 직접 보고, 타임스탬프·관찰·한계를 `watch-evidence.json`에 기록한다.
6. `balanced` 샘플은 전체 재생이나 고밀도 검토를 대신하지 않는다. 0.25초보다 빠른 컷, 작은 문구, 방향·트래킹·프리즈 판정은 Haku dense sheet와 전환 strip으로 재검토한다.
7. `public-reference-only` 결과는 분석 증거로만 유지하고 proof·final·promoted pack으로 복사하지 않는다.
8. 각 프레임 관찰을 schema 1.1 `timeline-grammar.json`의 이벤트 ID에 연결한다. 연결 전에는 `conversion.status=pending`, 연결 뒤에는 `mapped`로 기록한다.
9. 관찰과 추론을 분리한다. `/watch`의 자동 장면 선택 이유를 연출 의도로 오해하지 않는다.
10. `scripts/validate_watch_evidence.py WATCH_EVIDENCE --check-files`를 통과하지 못하면 해당 수집물을 Haku 직접 검토 완료 근거로 사용하지 않는다.

기본 호출 예시:

```powershell
tools\run-watch.cmd -RightsStatus public-reference-only "<URL>" --detail balanced --out-dir "<evidence-dir>"
```

로컬 무편집 원본 예시:

```powershell
tools\run-watch.cmd -RightsStatus licensed "<한글 경로\원본.mp4>" --detail balanced --no-whisper --out-dir "<evidence-dir>"
```

