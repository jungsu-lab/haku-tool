# Haku AutoResearch Compact Package

이 패키지는 약 2GB 전체 보관본에서 영상·이미지 바이너리와 중복 렌더를 제외한 소스 중심 버전이다.

## 포함

- Haku Tool `SKILL.md`, scripts, references, schemas, templates
- 40-Reel 연구 상태와 semantic review
- 4편·24개 이벤트 타임라인 문법
- Operator 레지스트리와 auto-research findings
- 25개 proof cycle의 recipe, critique, render report, review manifest
- 첫 사용자 승인 proof의 시간 구간별 10축·원본 frame mapping과 `density-wave-release` 승격 진행률 `1/3`
- 공개 무료 음원 권리 매니페스트·음악 사건표 템플릿과 검증기
- 최상위 작업 계약 `REFERENCE_BASED_VIDEO_WORK_CONTRACT.md`
- 소스 권리·선별 manifest
- 자동 테스트와 회귀 검증 파일

## 제외

- 공개 Haku Reel 원본
- 스톡 및 사용자 제공 원본 영상
- plain/proof/비교영상 렌더
- storyboard, dense sheet, boundary strip 이미지
- 렌더 중간 segment
- 음악 MP3 원본과 분석용 preview; rights manifest와 기술 fixture JSON만 포함
- 백업과 임시 출력

제외된 대표 Haku 원본 10편과 최신 plain/proof 비교영상은 `C:/Users/HP-5600G/Desktop/하쿠영상/` 및 `C:/Users/HP-5600G/Desktop/영상편집/haku-auto-research-review/`에 별도로 보존되어 있다.

## 재렌더

recipe의 `materials.*.source`가 가리키는 원본 영상은 compact ZIP에 포함되지 않는다. 원본 경로를 현재 PC의 촬영본 또는 라이선스가 확인된 소스로 연결한 뒤 렌더 스크립트를 실행한다.

외부 음악은 AI로 생성하지 않는다. 영상 동기화와 게시 목적에 맞는 무료 공개 트랙만 사용하고, 트랙 페이지·라이선스·저작자·파일 해시·표기 의무·Content ID 위험을 `audio-rights.json`에 남긴다. 음악과 화면의 상호작용은 `music-event-map.json`으로 별도 검증한다.

승격은 전역 승인 합계가 아니라 같은 tested Operator의 서로 다른 승인 상황 세 개로 계산한다. supporting Operator는 자동으로 같은 승인 수를 받지 않는다.
