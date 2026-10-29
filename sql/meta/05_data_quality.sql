-- meta.dq_rule is created by dbt seed from dbt_project/seeds/dq_rule.csv
CREATE TABLE IF NOT EXISTS meta.dq_notification (
    notification_key INTEGER, rule_key VARCHAR, notification_time TIMESTAMP, message VARCHAR
);
CREATE TABLE IF NOT EXISTS meta.dw_user (user_key INTEGER, user_name VARCHAR, role_name VARCHAR);
