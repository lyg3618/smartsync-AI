SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS contacts (
    id VARCHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200) NOT NULL DEFAULT '',
    user_id VARCHAR(50) NULL,
    username VARCHAR(50) NULL,
    hashed_password VARCHAR(255) NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_contacts_username (username),
    KEY idx_contacts_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meetings (
    id VARCHAR(36) NOT NULL,
    name VARCHAR(500) NOT NULL,
    date VARCHAR(20) NULL,
    duration_sec INT NOT NULL DEFAULT 0,
    task_count INT NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'ready_for_review',
    audio_url VARCHAR(1000) NULL,
    summary TEXT NULL,
    decisions JSON NULL,
    template_minutes LONGTEXT NULL,
    user_id VARCHAR(50) NULL,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    deleted_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_meetings_user_deleted_date (user_id, is_deleted, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS upload_tasks (
    id VARCHAR(36) NOT NULL,
    meeting_id VARCHAR(36) NULL,
    status VARCHAR(50) NULL,
    progress INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_upload_tasks_meeting (meeting_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS action_items (
    id INT NOT NULL AUTO_INCREMENT,
    meeting_id VARCHAR(36) NOT NULL,
    owner_id VARCHAR(36) NULL,
    owner_name VARCHAR(100) NULL,
    content TEXT NULL,
    due_date VARCHAR(20) NULL,
    status ENUM('pending', 'in_progress', 'done') NOT NULL DEFAULT 'pending',
    updated_after_dispatch TINYINT(1) NOT NULL DEFAULT 0,
    last_dispatched_at DATETIME NULL,
    is_viewed TINYINT(1) NOT NULL DEFAULT 0,
    viewed_at DATETIME NULL,
    completed_at DATETIME NULL,
    progress_note TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_action_items_meeting_updated (meeting_id, updated_after_dispatch),
    KEY idx_action_items_owner (owner_id),
    CONSTRAINT fk_action_items_meeting
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS transcripts (
    id INT NOT NULL AUTO_INCREMENT,
    meeting_id VARCHAR(36) NOT NULL,
    start_ms BIGINT NOT NULL DEFAULT 0,
    end_ms BIGINT NOT NULL DEFAULT 0,
    text TEXT NULL,
    speaker VARCHAR(64) NOT NULL DEFAULT 'SPEAKER_00',
    confidence FLOAT NULL,
    segment_no INT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    KEY idx_transcripts_meeting_start (meeting_id, start_ms),
    KEY idx_transcripts_meeting_speaker (meeting_id, speaker),
    CONSTRAINT fk_transcripts_meeting
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meeting_minutes_templates (
    id INT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    name VARCHAR(120) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    is_default TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_minutes_templates_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS llm_connection_configs (
    id INT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    name VARCHAR(120) NOT NULL,
    model VARCHAR(120) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    api_key VARCHAR(500) NOT NULL DEFAULT '',
    is_active TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_llm_configs_user_updated (user_id, updated_at),
    KEY idx_llm_configs_user_active (user_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'system',
    related_type VARCHAR(50) NULL,
    related_id VARCHAR(100) NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_notifications_user_created (user_id, created_at),
    KEY idx_notifications_user_read (user_id, is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS system_settings (
    `key` VARCHAR(100) NOT NULL,
    `value` JSON NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO system_settings (`key`, `value`)
VALUES ('dispatch_channels', JSON_OBJECT('email_enabled', TRUE))
ON DUPLICATE KEY UPDATE `key` = VALUES(`key`);
