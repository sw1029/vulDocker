# 도메인 지식 베이스 가이드

TODO 18(도메인 지식 베이스 구축)와 prompt.md 부록/14장을 기반으로 SQLi 등 취약 패턴을 체계화한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 자료 출처
- SQLi 분류 서베이: Halfond et al., "A Classification of SQL Injection Attacks".
- Juliet 1.3 Test Suite (SAMATE/NIST) – 회귀 테스트.
- CWE/OWASP 공식 자료.
- 사내 축적 로그/패턴 메모.

## 2. 템플릿 규칙화
- **SQLi 패턴 ID 예시**
  - `sqli-string-concat`: 문자열 연결 기반 raw query.
  - `sqli-orm-raw`: ORM에서 raw query 허용.
  - `sqli-encoding-bypass`: 인코딩/로케일 변형.
- 각 템플릿은 언어/프레임워크/DB 조합과 입력 채널을 정의한다.
- 템플릿 메타데이터 예시:
```json
{
  "pattern_id": "sqli-string-concat",
  "language": "Python",
  "framework": "Flask",
  "db": "MySQL",
  "payload_examples": ["' OR '1'='1"],
  "defense_gap": "미검증 문자열",
  "references": ["Halfond2006"]
}
```

## 3. Juliet 활용
- `rag/corpus/raw/juliet/`에 Juliet 테스트케이스 수집.
- 취약/비취약 페어를 라벨링하여 메타모픽 테스트, 회귀 평가에 사용.
- Juliet 버전/변경사항은 `metadata/juliet_versions.json`에 기록.

## 4. 구성 디렉토리
```
rag/corpus/
  raw/
    public/
    poc/
    internal/
    juliet/
  processed/<snapshot>/
  templates/
    sql_injection/
    xss/
```
- 각 템플릿 폴더에 README, 예제 코드, 참고 링크 포함.

## 5. 정합성 체크
- [x] prompt.md 14장(도메인 지식 베이스) 반영.
- [x] docs/rag/design.md와 corpus 구조 일치.
- [x] Variation/Scenario ID 설계와 패턴 메타데이터 연결.

## 연관 문서
- `docs/rag/design.md`
- `docs/rag/snapshots.md`
- `docs/variability_repro/design.md`
