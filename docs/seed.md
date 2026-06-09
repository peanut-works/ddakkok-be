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
password_hash: test-password-hash
name: 테스트교사
role: TEACHER
facility_id: 1
```

`password_hash`는 BE-08 로그인 구현 전 임시 seed 값입니다.

## 결과 확인

테이블별 row count 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "SELECT 'facilities' AS table_name, COUNT(*) FROM facilities UNION ALL SELECT 'classrooms', COUNT(*) FROM classrooms UNION ALL SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'children', COUNT(*) FROM children UNION ALL SELECT 'child_health_profiles', COUNT(*) FROM child_health_profiles UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'ingredient_aliases', COUNT(*) FROM ingredient_aliases UNION ALL SELECT 'safety_rules', COUNT(*) FROM safety_rules ORDER BY table_name;"
```

테스트 계정 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "SELECT id, email, name, role, facility_id FROM users;"
```

아동 수 확인:

```bash
docker compose exec db psql -U ddakkok -d ddakkok -c "SELECT COUNT(*) FROM children;"
```
