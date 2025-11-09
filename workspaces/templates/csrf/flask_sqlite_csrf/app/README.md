# Flask + SQLite CSRF (CWE-352)

- `/transfer`는 CSRF 토큰 검증 없이 POST 요청만으로 상태 변경(잔액 감소 및 FLAG 반환)을 수행합니다.
- 데이터베이스는 로컬 SQLite 파일(`/tmp/csrf_app.db`).
- PoC: `python poc.py --base-url http://127.0.0.1:5000 --amount 100`.

## Files
- `app.py` – 취약 Flask 서비스.
- `schema.sql` – 초기 데이터 및 FLAG 삽입.
- `poc.py` – 토큰 없이 POST를 보내 FLAG 유출 여부를 확인.
- `Dockerfile`, `requirements.txt` – 재현용 런타임 정의.

