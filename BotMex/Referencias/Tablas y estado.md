# Referencias — Tablas y Estado de BD

Base de datos canónica: `betmexico_accounts.db` (SQLite WAL).

### Tablas Principales
1. **`accounts`**:
   - `id`, `username`, `password`, `jwt_token`, `balance`, `status` (`ready`, `hot`, `rate_limited`, `DEAD`).
   - `is_married` (0/1), `married_card_id`, `last_checked`.
2. **`missions`**:
   - `id`, `created_at`, `status` (`preparing`, `active`, `completed`, `failed`), `progress_pct`.
   - `operator_id`, `accounts_count`, `approved_count`.
3. **`cards`**:
   - `id`, `pan`, `bin`, `exp`, `cvv`, `status` (`available`, `burned`, `married`).
4. **`deposits`**:
   - `id`, `account_id`, `card_id`, `amount`, `status`, `response_code`, `created_at`.
