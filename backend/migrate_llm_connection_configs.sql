CREATE TABLE IF NOT EXISTS llm_connection_configs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(50) NOT NULL,
  name VARCHAR(120) NOT NULL,
  model VARCHAR(120) NOT NULL,
  base_url VARCHAR(255) NOT NULL,
  api_key VARCHAR(255) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_connection_configs_user_updated
  ON llm_connection_configs(user_id, updated_at);

CREATE INDEX idx_llm_connection_configs_user_active
  ON llm_connection_configs(user_id, is_active);
