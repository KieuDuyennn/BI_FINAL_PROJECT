CREATE TABLE IF NOT EXISTS meta.dq_rule (
    rule_key VARCHAR, rule_name VARCHAR, rule_description VARCHAR, rule_type VARCHAR,
    rule_category VARCHAR, risk_level INTEGER, action VARCHAR, status VARCHAR
);
CREATE TABLE IF NOT EXISTS meta.dq_notification (
    notification_key INTEGER, rule_key VARCHAR, notification_time TIMESTAMP, message VARCHAR
);
CREATE TABLE IF NOT EXISTS meta.dw_user (user_key INTEGER, user_name VARCHAR, role_name VARCHAR);
