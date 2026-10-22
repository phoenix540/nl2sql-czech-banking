#!/bin/bash
# Cree l'utilisateur lecture seule utilise par le moteur NL-to-SQL.
# Meme si le LLM generait un DROP/DELETE, la base le refuserait.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE ROLE ${RO_USER} LOGIN PASSWORD '${RO_PASSWORD}';
  ALTER ROLE ${RO_USER} SET statement_timeout = '10s';
  ALTER ROLE ${RO_USER} SET default_transaction_read_only = on;
  GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${RO_USER};
  GRANT USAGE ON SCHEMA public TO ${RO_USER};
  GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${RO_USER};
  ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_USER} IN SCHEMA public
        GRANT SELECT ON TABLES TO ${RO_USER};
EOSQL
