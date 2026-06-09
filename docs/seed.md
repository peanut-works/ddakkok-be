# Seed Data

BE-05 seed 데이터와 실행 방법을 정리한 문서입니다.

## 실행 전제

Docker Compose로 backend와 db가 실행 중이어야 합니다.

```bash
docker compose up -d --build
```

Alembic migration이 먼저 적용되어 있어야 합니다.

```bash
docker compose exec backend uv run --no-sync alembic upgrade head
```

현재 적용된 revision 확인:

```bash
docker compose exec backend uv run --no-sync alembic current
```

DB 테이블 목록 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "\dt"
```

## Seed 실행

```bash
docker compose exec backend uv run --no-sync python scripts/seed.py
```

Seed script는 아래 seed 대상 테이블 데이터를 비우고 다시 삽입합니다.

```text
facilities
classrooms
users
children
child_health_profiles
products
ingredient_aliases
safety_rules
```

## 현재 Seed 구성

```text
facilities: 1
classrooms: 2
users: 1
children: 10
child_health_profiles: 10
products: 9
ingredient_aliases: 18
safety_rules: 8
```

제품 데이터는 성분 관련 공공 API 기반 데이터가 포함되어 있어 임의로 추가하지 않았습니다.

## 테스트 계정

```text
email: teacher@ddakkok.com
password: ddakkok1234
password_hash: plain:ddakkok1234
name: 김하늘
role: TEACHER
facility_id: 1
classroom_id: 1
```

`password_hash`는 BE-08 데모 로그인을 위한 임시 plain prefix 값입니다.
실제 배포 인증에서는 bcrypt/argon2 기반 hash로 교체해야 합니다.

## 로그인 API

이메일/시설 계정 로그인:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@ddakkok.com","password":"ddakkok1234","login_method":"FACILITY"}'
```

체험하기 로그인:

```bash
curl -X POST http://localhost:8000/api/auth/demo
```

로그인 사용자 정보 확인:

```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer mock-token:user:1"
```

카카오 로그인은 OAuth callback 서버 설정이 준비된 뒤 구현합니다.

## 결과 확인

테이블별 row count 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "SELECT 'facilities' AS table_name, COUNT(*) FROM facilities UNION ALL SELECT 'classrooms', COUNT(*) FROM classrooms UNION ALL SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'children', COUNT(*) FROM children UNION ALL SELECT 'child_health_profiles', COUNT(*) FROM child_health_profiles UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'ingredient_aliases', COUNT(*) FROM ingredient_aliases UNION ALL SELECT 'safety_rules', COUNT(*) FROM safety_rules ORDER BY table_name;"
```

테스트 계정 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "SELECT id, email, name, role, facility_id, classroom_id FROM users;"
```

아동 수 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "SELECT COUNT(*) FROM children;"
```
