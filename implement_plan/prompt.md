다음은 “자율 AI 에이전트 기반 온디맨드 취약점 테스트베드 생성”을 실현하기 위한 **구현안**이다. 코드는 제외하고 **논리 구조, 사용 모델, 프로젝트 구성, 운영 전략, 다변성·재현성 확보책**을 단계별로 정리한다.

---

## 1) 목표와 출력 정의

* **입력**: 취약점 요구(예: CWE‑89, 특정 CVE, 취약 패턴 설명).
* **핵심 출력물**

  1. **취약 환경 아티팩트**: Docker 이미지 또는 MicroVM 이미지. SBOM 포함.
  2. **PoC 검증 스크립트**: 익스플로잇 성공을 자동 판정.
  3. **재현 리포트**: 실행 로그, 환경 해시, 모델·프롬프트·시드, RAG 스냅샷 ID.
  4. **메타데이터**: 취약점 메타, 시나리오 파라미터, 평가 지표.
* **성공 기준**: PoC가 기대 행위 달성. 로그와 트레이스가 남음. 동일 시드로 재실행 시 일치. 다양한 시나리오군을 일정 비율 이상 커버.

---

## 2) 전반 아키텍처

### 2.1 에이전트 + 실행기

* **Researcher**: 외부 자료 검색·요약 RAG 리포트 생성. ReAct 스타일 도구 호출 허용. Reflexion식 언어적 반성 메모리로 다음 시도 개선. ([arXiv][1])
* **Generator**: 소스·Dockerfile·설정·PoC 초안 생성. Reviewer 피드백 반영.
* **Reviewer**: 실행 로그와 코드 동시 분석. 구체적 수정 지시 생성.
* **Executor**: 격리 샌드박스에서 build/run/PoC 실행. STDOUT/STDERR와 측정치 반환.

### 2.2 오케스트레이션

* **상태 기계**: `PLAN → DRAFT → BUILD → RUN → VERIFY → REVIEW → (수정 루프) → PACK`
* **중앙 메타스토어**: 모든 단계의 아티팩트와 해시를 버전 관리.
* **트레이싱**: OpenTelemetry + W3C Trace Context로 시도별 원인 추적. ([W3C][2])

---

## 3) 데이터 흐름과 스키마(요약)

### 3.1 Researcher 출력(RAG 보고서, JSON)

```
{ vuln_id, intent, preconditions, tech_stack_candidates[], minimal_repro_steps[],
  references[], pocs[], deps[], risks[], retrieval_snapshot_id }
```

* **근거**: RAG로 외부 지식 보강. ([arXiv][3])
* 도구 사용 방식은 ReAct(추론·행동 상호작용), 실패 시 Reflexion 메모리로 재시도. ([arXiv][1])

### 3.2 Reviewer 버그리포트

```
{ file, line, issue, fix_hint, test_change, severity, evidence_log_ids[] }
```

### 3.3 Executor 결과

```
{ build_log, run_log, verify_pass(bool), traces, coverage?, resource_usage }
```

### 3.4 패키징 메타

```
{ scenario_id, seed, model_version, prompt_hash, retriever_commit,
  base_image_digest, sbom_ref, safety_gates[], timestamps }
```

---

## 4) 모델·툴 선택 원칙

* **LLM 조합**: 주 모델 1개(코드·도구 사용 강점), 보조 모델 1개(리뷰·체크리스트).
* **디코딩 전략**:

  * **재현 모드**: greedy 또는 temperature=0.
  * **다변성 모드**: top‑p 샘플링과 self‑consistency 투표. 의미: 다양한 추론 경로를 샘플링해 다수결로 결론을 정함. ([arXiv][4])
* **멀티에이전트 프레임워크**: AutoGen류 대화형 에이전트 패턴을 참고. ([arXiv][5])
* **성능 측정 참고**: 코드 작업 난이도 지표로 SWE‑bench 동향을 모니터링. ([arXiv][6])

---

## 5) RAG 설계

* **코퍼스 층위**

  1. 공용 지식: CWE, OWASP, Juliet 등. Juliet은 취약 예제의 체계적 셋 제공. ([NIST][7])
  2. 최신 PoC 검색: CVE 참고 링크, 블로그, 논문.
* **색인**: 패턴 인식이 필요한 문서는 함수 단위로 청킹.
* **스냅샷**: 리트리버 인덱스 커밋 고정. 보고서에 `retrieval_snapshot_id` 포함.
* **반복 개선**: 실패 로그를 쿼리 증강에 반영(Reflexion). ([OpenReview][8])

---

## 6) 보안 샌드박스 계층

* **격리 우선순위**: MicroVM 우선(Firecracker, Kata Containers). 사용자 공간 커널(gVisor)은 호환성·성능 절충. 연구 결과와 트레이드오프를 문서화. ([USENIX][9])
* **구성**

  * 실행기 Pod: rootless, seccomp, read‑only FS, no‑privilege.
  * 네트워크: 기본 이그레스 차단. 필요 도메인만 허용.
  * 이미지: 베이스 이미지 고정 다이제스트. SBOM 생성(SPDX 또는 CycloneDX). ([SPDX][10])
* **취약 환경 공급망 보안**: SBOM 내 컴포넌트 버전, CVE 참조, 빌드 레시피 기록. CycloneDX 1.5는 ML·구성 자산도 표현 가능. ([CycloneDX][11])
* **한계 인지**: MicroVM 기반 격리도 탈출 공격 연구가 존재. 완화책으로 커널·VMM 주기 패치, 하드닝 프로파일 유지. ([USENIX][12])

---

## 7) **다변성**과 **재현성**을 함께 확보하는 전략

### 7.1 시나리오 공간의 체계화

* **차원 테이블**(예): 언어, 웹 프레임워크, DB 타입, ORM 유무, 인코딩, 인증, 배포 형태, OS, 로케일, 입력 채널, 필터 위치, 스키마 운용(ORM vs raw SQL) 등.
* **샘플링**: 라틴 하이퍼큐브 샘플링(LHS)으로 균형 있게 조합을 선택. 의미: 각 차원의 구간을 고르게 커버해 표본 편향을 줄임. ([JSTOR][13])

### 7.2 출력 다양화 제어(모델 레벨)

* **확률적 디코딩**: top‑p, temperature, nucleus sampling. 의미: 확률 질량의 핵심 부분에서만 샘플링해 품질 유지하며 다양성 확보. ([OpenReview][14])
* **Self‑Consistency**: 서로 다른 추론 경로를 다중 샘플링 후 합의. 동일 요구라도 내부 경로 다양화. ([arXiv][15])

### 7.3 템플릿·패턴 레벨

* **패턴 풀**: 동일 CWE에 대해 서로 다른 코드 패턴과 프레임워크 템플릿을 다수 보유. 예: SQLi는 문자열 연결형, 매개변수 무효화형, ORM raw‑query 남용형 등. 분류 서베이 기반으로 패턴 정의. ([Viterbi School of Engineering][16])
* **패턴 선택기**: LHS 샘플과 사용자 힌트를 함께 고려해 패턴을 고른다.

### 7.4 환경 레벨

* **의존 버전 가중치**: 서로 다른 DB, 드라이버, 커넥션 모드 선택을 확률적으로 가중.
* **데이터 셋 변이**: 스키마 명명, 로케일, 유니코드, 정렬 규칙 등 입력 유틸리티 변화.

### 7.5 재현성 캡슐화

* **Scenario ID**: 모든 결정요인에 대한 내용 주소 해시로 생성.

  * 의미: 같은 입력과 파라미터면 같은 ID와 아티팩트가 생성.
  * 정의: `SID = H(model_ver || prompts_hash || seed || retriever_commit || corpus_snapshot || pattern_id || deps_digest || base_image_digest)`
* **고정 요소**: 모델 버전, 프롬프트, 리트리버 스냅샷, 베이스 이미지, SBOM, LHS 시드.
* **결과 캐시**: `SID` 키로 결과를 캐시해 **같은 요구는 같은 결과**를 보장.
* **다변성 요구 시**: `variation_key`만 변경. 나머지는 고정.

  * 예: `variation_key = {top_p, temp, self_consistency_k, pattern_pool_seed}`

### 7.6 **다변성 지표**와 **재현성 지표**

* **샤논 엔트로피**로 패턴 선택 분포의 다양성 측정. 의미: 값이 높을수록 선택이 고르게 분산.

  * (H = -\sum_i p_i \log p_i)
* **시나리오 거리**: 차원별 해밍 거리의 정규화 합.
* **재현율**: 동일 `(requirement, SID)` 재실행 시 동일 아티팩트가 나오는 비율.

---

## 8) 자동 검증과 평가

* **PoC 기반 판정**: 익스플로잇 성공 조건을 명세화.
* **메타모픽 테스트**: 입력 변환에도 취약 동작이 보존되는지 확인. 예: SQLi에서 공백·주석·대소문 변형 후에도 성공해야 함. 개념 근거는 메타모픽 테스팅. ([HKUST CSE][17])
* **정적 분석**: 단순 신호(하드코딩 크리덴셜, 위험 API 사용).
* **커버리지**: PoC 실행 중 취약 경로가 실제로 실행됐는지 추적.
* **코드 작업 난이도 벤치 참고**: SWE‑bench 결과를 내부 QA의 외부 비교선으로 사용. ([arXiv][6])

---

## 9) 운영·관측·감사

* **분산 트레이싱**: 오케스트레이션 단계와 각 도구 호출에 TraceId 부여. 포렌식에 유리. ([OpenTelemetry][18])
* **로그 표준화**: 단계, 에이전트, 시드, 패턴, 해시, 리소스 사용량.
* **보안 게이트**:

  1. 의심 페이로드 차단 목록,
  2. 외부 네트워크 제한,
  3. 이미지 스캐닝,
  4. 서드파티 PoC 실행 금지 규칙.

---

## 10) 프로젝트 구성(폴더와 서비스)

```
/orchestrator     : 상태기계, 큐, 리트라이, 트레이싱 훅
/agents
  /researcher     : 웹검색, RAG 리포트 생성
  /generator      : 산출물 초안 생성
  /reviewer       : 로그·코드 분석, 수정지시 생성
/executor
  /runtime        : Firecracker/Kata/gVisor 구동 어댑터
  /policies       : seccomp, AppArmor, 네트워크 정책
/rag
  /corpus         : CWE, 논문, 샘플, 사내 위키
  /index          : 인덱스 스냅샷, 커밋
  /retriever      : 검색기, 랭커
/artifacts        : 이미지, SBOM, 로그, 트레이스
/metadata         : Scenario ID, LHS 시드, 파라미터
/evals            : PoC 판정, 메타모픽 테스트 세트
/ops
  /ci             : 이미지 고정, 재현성 체크
  /observability  : OTEL, 대시보드
```

* **실행기 선택 가이드**

  * **최고 격리**: Firecracker 또는 Kata(microVM). 성능 비용 수반. ([USENIX][9])
  * **호환성·속도**: gVisor. 일부 오버헤드·호환성 이슈 인지. ([USENIX][19])

---

## 11) 단계별 구축 로드맵

1. **MVP**

   * 단일 LLM, 정적 RAG 샘플 1종, 로컬 실행기.
   * 목표: `생성 → 검증 → 수정` 루프가 한 번이라도 닫히는지.
2. **핵심 안정화**

   * Generator·Reviewer 분리. Docker 격리. SQLi 같은 DB 연동형 취약점 확대.
3. **고도화**

   * Researcher 추가. 외부 검색 도구와 ReAct 연동. 최신 CVE에서 테스트베드 자가 생성 검증. ([arXiv][1])

---

## 12) 위험과 완화

* **격리 실패 위험**: 마이크로VM과 정책 하드닝. 최신 보안 연구 모니터링. ([USENIX][12])
* **환각·오분석 위험**: Reflexion식 피드백 메모리로 반복 개선. Reviewer를 상위 성능 모델로 배정. ([OpenReview][8])
* **출력 단조로움**: LHS + 패턴 풀 + 확률 디코딩 조합으로 다양성 유지. ([Taylor & Francis Online][20])
* **재현 실패**: SID 기반 캐시, 스냅샷, 버전 고정, deterministic 모드.

---

## 13) 핵심 지표(KPI)

* **Exploit 성공률**: PoC 기준.
* **루프 수·수정 횟수**: 평균 N회 이하.
* **시나리오 다양성**: 엔트로피 H, 차등 커버 비율.
* **재현율**: 동일 `(requirement, SID)` 재실행 일치율.
* **안전도**: 외부 네트워크 차단율, 정책 위반 0건.

---

## 14) 취약점 도메인 지식 베이스 초안

* **SQLi 레퍼런스**: 공격 유형과 방어 분류 서베이 활용. 템플릿 파생 규칙 도출. ([Viterbi School of Engineering][16])
* **웹 취약 예제 묶음**: Juliet 1.3 활용해 회귀·회복 평가. ([NIST][21])

---

## 15) 운영 정책

* **윤리·컴플라이언스**: 외부 타깃 공격 금지. 내부 샌드박스만 허용.
* **배포**: 전용 클러스터. 빌드 시 SBOM 생성과 서명. SPDX 또는 CycloneDX 문서화. ([SPDX][10])
* **관측 대시보드**: 트레이스, 성공률, 다양성 지표, 자원 사용량.

---

### 부록 A. 용어 근거 문헌 요약

* **RAG 기본**: 외부 지식 결합으로 사실성 향상. ([arXiv][3])
* **ReAct 패턴**: 추론과 행동을 교차. 도구 사용에 적합. ([arXiv][22])
* **Reflexion**: 언어적 강화로 반복 개선. ([arXiv][23])
* **Self‑Consistency**: 다중 경로 샘플 후 합의. ([arXiv][15])
* **다변성 샘플링**: nucleus(top‑p)로 다양성 확보. ([OpenReview][14])
* **MicroVM 격리**: Firecracker·Kata의 설계 근거. gVisor 연구 비교. ([USENIX][9])
* **메타모픽 테스트**: 오라클 문제 완화. ([HKUST CSE][17])
* **샘플링 설계**: LHS. ([JSTOR][13])
* **SBOM 표준**: SPDX, CycloneDX. ([SPDX][10])

---

## 마무리

핵심은 **패턴화된 시나리오 공간 + 확률적 생성 제어 + 강한 스냅샷과 해시 기반 재현**이다. 이 삼각 구성을 유지하면, 같은 요구에 대해 **원하면 동일 결과**, **원하면 다양한 결과**를 모두 달성할 수 있다.

[1]: https://arxiv.org/pdf/2210.03629?utm_source=chatgpt.com "ReAct: Synergizing Reasoning and Acting in Language ..."
[2]: https://www.w3.org/TR/trace-context/?utm_source=chatgpt.com "Trace Context"
[3]: https://arxiv.org/abs/2005.11401?utm_source=chatgpt.com "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
[4]: https://arxiv.org/abs/1904.09751?utm_source=chatgpt.com "The Curious Case of Neural Text Degeneration"
[5]: https://arxiv.org/abs/2308.08155?utm_source=chatgpt.com "AutoGen: Enabling Next-Gen LLM Applications via Multi- ..."
[6]: https://arxiv.org/abs/2310.06770?utm_source=chatgpt.com "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"
[7]: https://www.nist.gov/publications/juliet-11-cc-and-java-test-suite?utm_source=chatgpt.com "The Juliet 1.1 C/C++ and Java Test Suite"
[8]: https://openreview.net/pdf?id=vAElhFcKW6&utm_source=chatgpt.com "Language Agents with Verbal Reinforcement Learning"
[9]: https://www.usenix.org/system/files/nsdi20-paper-agache.pdf?utm_source=chatgpt.com "Firecracker: Lightweight Virtualization for Serverless ..."
[10]: https://spdx.github.io/spdx-spec/v2.3/?utm_source=chatgpt.com "SPDX Specification 2.3.0"
[11]: https://cyclonedx.org/news/cyclonedx-v1.5-released/?utm_source=chatgpt.com "Introducing OWASP CycloneDX v1.5 - Advanced Bill of ..."
[12]: https://www.usenix.org/system/files/usenixsecurity23-xiao-jietao.pdf?utm_source=chatgpt.com "Breaking the Isolation of MicroVM-based Containers ..."
[13]: https://www.jstor.org/stable/1268522?utm_source=chatgpt.com "A Comparison of Three Methods for Selecting Values of ..."
[14]: https://openreview.net/pdf?id=rygGQyrFvH&utm_source=chatgpt.com "THE CURIOUS CASE OF NEURAL TEXT DeGENERATION"
[15]: https://arxiv.org/pdf/2203.11171?utm_source=chatgpt.com "Self-Consistency Improves Chain of Thought Reasoning in ..."
[16]: https://viterbi-web.usc.edu/~halfond/papers/halfond06issse.pdf?utm_source=chatgpt.com "A Classification of SQL Injection Attacks and ..."
[17]: https://www.cse.ust.hk/faculty/scc/publ/CS98-01-metamorphictesting.pdf?utm_source=chatgpt.com "A New Approach for Generating Next Test Cases y"
[18]: https://opentelemetry.io/docs/concepts/context-propagation/?utm_source=chatgpt.com "Context propagation"
[19]: https://www.usenix.org/system/files/hotcloud19-paper-young.pdf?utm_source=chatgpt.com "The True Cost of Containing: A gVisor Case Study"
[20]: https://www.tandfonline.com/doi/abs/10.1080/00401706.1987.10488205?utm_source=chatgpt.com "Large Sample Properties of Simulations Using Latin ..."
[21]: https://samate.nist.gov/SARD/downloads/documents/Juliet_1.3_Changes_From_1.2.pdf?utm_source=chatgpt.com "Juliet 1.3 Test Suite: Changes From 1.2 - SAMATE | NIST"
[22]: https://arxiv.org/abs/2210.03629?utm_source=chatgpt.com "Synergizing Reasoning and Acting in Language Models"
[23]: https://arxiv.org/abs/2303.11366?utm_source=chatgpt.com "Reflexion: Language Agents with Verbal Reinforcement Learning"
