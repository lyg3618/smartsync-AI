CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    category VARCHAR(50) NOT NULL DEFAULT 'system',
    related_type VARCHAR(50) NULL,
    related_id VARCHAR(100) NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_notifications_user_created (user_id, created_at DESC),
    INDEX idx_notifications_user_read (user_id, is_read, created_at DESC)
);
