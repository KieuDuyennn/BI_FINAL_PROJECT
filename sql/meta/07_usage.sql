CREATE TABLE IF NOT EXISTS meta.usage_log (
    usage_log_key BIGINT, user_name VARCHAR, object_name VARCHAR, accessed_at TIMESTAMP, purpose VARCHAR
);
-- TODO: document/report dashboard and query usage after deployment.
