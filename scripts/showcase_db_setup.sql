-- Run with psql as the instance administrator; no password is embedded here.
-- Configure authentication separately via the deployment's secret mechanism.
-- Exclude alea_showcase from every instance backup job.
\set ON_ERROR_STOP on
SELECT 'CREATE ROLE alea_showcase LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'alea_showcase') \gexec
ALTER ROLE alea_showcase NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;
SELECT 'CREATE DATABASE alea_showcase OWNER alea_showcase'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'alea_showcase') \gexec
REVOKE ALL ON DATABASE alea_showcase FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE alea_showcase TO alea_showcase;
-- Do not touch other databases' ACLs on this shared instance. The showcase
-- role may be able to CONNECT to another database through PUBLIC, but it has
-- no grants on any other database's tables, so it cannot read their data.
-- Refuse inherited memberships that could re-enable cross-database access.
SELECT format('REVOKE %I FROM alea_showcase', parent.rolname)
FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid
JOIN pg_roles member ON member.oid=m.member
WHERE member.rolname='alea_showcase' \gexec
