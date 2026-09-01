-- 按需求文档 8.2 创建缺失的 AI 域 4 张表（幂等）
CREATE TABLE IF NOT EXISTS ai_kb_doc (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL COMMENT '文档标题',
    file_url VARCHAR(255) NULL COMMENT 'MinIO 对象路径',
    category VARCHAR(64) NULL COMMENT '分类',
    chunk_count INT DEFAULT 0 COMMENT '切片数',
    status INT DEFAULT 1 COMMENT '1正常 0停用',
    created_by INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档(AI-4)';

CREATE TABLE IF NOT EXISTS ai_kb_chunk (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id INT NOT NULL COMMENT '所属文档',
    chunk_index INT DEFAULT 0,
    content TEXT COMMENT '切片内容',
    embedding_id VARCHAR(128) NULL COMMENT 'Milvus kb_vec 向量键',
    INDEX idx_doc_id (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档切片(AI-4)';

CREATE TABLE IF NOT EXISTS ai_conversation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    type VARCHAR(16) DEFAULT 'chat' COMMENT 'rag/nl2sql/chat',
    question TEXT,
    answer TEXT,
    chart_json TEXT,
    tokens INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问答/问数记录(AI-6)';

CREATE TABLE IF NOT EXISTS ai_prompt (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) UNIQUE COMMENT '模板编码',
    name VARCHAR(128) NULL,
    content TEXT,
    params TEXT,
    status INT DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Prompt 模板(AI-7)';
