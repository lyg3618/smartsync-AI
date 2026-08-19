-- smartsync.contacts definition

CREATE TABLE `contacts` (
                            `id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                            `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                            `email` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
                            `user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            `hashed_password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            `role` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT 'user',
                            `collab_no` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            PRIMARY KEY (`id`) USING BTREE,
                            UNIQUE KEY `username` (`username`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC;


-- smartsync.llm_connection_configs definition

CREATE TABLE `llm_connection_configs` (
                                          `id` int NOT NULL AUTO_INCREMENT,
                                          `user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                          `name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                          `model` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                          `base_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                          `api_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                          `is_active` tinyint(1) NOT NULL DEFAULT '0',
                                          `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                          `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                          PRIMARY KEY (`id`) USING BTREE,
                                          KEY `idx_llm_connection_configs_user_updated` (`user_id`,`updated_at`) USING BTREE,
                                          KEY `idx_llm_connection_configs_user_active` (`user_id`,`is_active`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;


-- smartsync.meeting_minutes_templates definition

CREATE TABLE `meeting_minutes_templates` (
                                             `id` int NOT NULL AUTO_INCREMENT,
                                             `user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                             `name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                             `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                             `is_default` tinyint(1) NOT NULL DEFAULT '0',
                                             `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                             `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                             PRIMARY KEY (`id`) USING BTREE,
                                             KEY `idx_minutes_templates_user_updated` (`user_id`,`updated_at`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;


-- smartsync.meetings definition

CREATE TABLE `meetings` (
                            `id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                            `name` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                            `date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            `duration_sec` int DEFAULT '0',
                            `task_count` int DEFAULT '0',
                            `status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT 'ready_for_review',
                            `audio_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            `summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
                            `decisions` json DEFAULT NULL,
                            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
                            `user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                            `is_deleted` tinyint(1) NOT NULL DEFAULT '0',
                            `deleted_at` datetime DEFAULT NULL,
                            `template_minutes` longtext,
                            PRIMARY KEY (`id`) USING BTREE,
                            KEY `idx_meetings_user_deleted_date` (`user_id`,`is_deleted`,`date`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC;


-- smartsync.notifications definition

CREATE TABLE `notifications` (
                                 `id` bigint NOT NULL AUTO_INCREMENT,
                                 `user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                 `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                 `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                                 `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'system',
                                 `related_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                                 `related_id` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                                 `is_read` tinyint(1) NOT NULL DEFAULT '0',
                                 `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                 `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                 PRIMARY KEY (`id`) USING BTREE,
                                 KEY `idx_notifications_user_created` (`user_id`,`created_at` DESC) USING BTREE,
                                 KEY `idx_notifications_user_read` (`user_id`,`is_read`,`created_at` DESC) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=111 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;


-- smartsync.system_settings definition

CREATE TABLE `system_settings` (
                                   `key` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                                   `value` json DEFAULT NULL,
                                   `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                   PRIMARY KEY (`key`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;


-- smartsync.upload_tasks definition

CREATE TABLE `upload_tasks` (
                                `id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                                `meeting_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `progress` int DEFAULT '0',
                                `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC;


-- smartsync.action_items definition

CREATE TABLE `action_items` (
                                `id` int NOT NULL AUTO_INCREMENT,
                                `meeting_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `owner_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `owner_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
                                `due_date` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `status` enum('pending','in_progress','done') NOT NULL DEFAULT 'pending',
                                `updated_after_dispatch` tinyint(1) NOT NULL DEFAULT '0',
                                `last_dispatched_at` datetime DEFAULT NULL,
                                `is_viewed` tinyint(1) NOT NULL DEFAULT '0',
                                `viewed_at` datetime DEFAULT NULL,
                                `completed_at` datetime DEFAULT NULL,
                                `progress_note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
                                `collab_message_target_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                                `collab_message_sent_at` datetime DEFAULT NULL,
                                `collab_message_deleted_at` datetime DEFAULT NULL,
                                `collab_message_title` varchar(255) DEFAULT NULL,
                                `collab_message_context` text,
                                `collab_message_login_id` varchar(100) DEFAULT NULL,
                                PRIMARY KEY (`id`) USING BTREE,
                                KEY `idx_action_items_meeting_updated` (`meeting_id`,`updated_after_dispatch`) USING BTREE,
                                CONSTRAINT `action_items_ibfk_1` FOREIGN KEY (`meeting_id`) REFERENCES `meetings` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=130 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC;


-- smartsync.transcripts definition

CREATE TABLE `transcripts` (
                               `id` int NOT NULL AUTO_INCREMENT,
                               `meeting_id` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                               `start_ms` int DEFAULT NULL,
                               `end_ms` int DEFAULT NULL,
                               `text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
                               `speaker` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'SPEAKER_00',
                               `confidence` float DEFAULT NULL,
                               `segment_no` int NOT NULL DEFAULT '0',
                               PRIMARY KEY (`id`) USING BTREE,
                               KEY `idx_transcripts_meeting_start` (`meeting_id`,`start_ms`) USING BTREE,
                               KEY `idx_transcripts_meeting_speaker` (`meeting_id`,`speaker`) USING BTREE,
                               CONSTRAINT `transcripts_ibfk_1` FOREIGN KEY (`meeting_id`) REFERENCES `meetings` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=635 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC;


